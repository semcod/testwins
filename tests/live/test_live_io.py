import asyncio
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
import http.client
import pytest
from PIL import Image,ImageDraw
from testwins.live.store import Store
from testwins.live.server import Server
from testwins.live.export import export
from testwins.live.native import NativeScanner
from testwins.live.config import Target,WatchConfig
from testwins.util import atomic_json,file_digest

ROOT=Path(__file__).resolve().parents[2]


def test_http_readonly_status_and_sse(tmp_path):
    store=Store(tmp_path/'db');store.emit('example',{'safe':'<script>'});server=Server(store,port=0);server.start()
    try:
        c=http.client.HTTPConnection('127.0.0.1',server.port,timeout=3);c.request('GET','/api/status');r=c.getresponse();assert r.status==200;assert json.loads(r.read())['last_event']==1;c.close()
        c=http.client.HTTPConnection('127.0.0.1',server.port,timeout=3);c.request('POST','/');r=c.getresponse();assert r.status==405;r.read();c.close()
        c=http.client.HTTPConnection('127.0.0.1',server.port,timeout=3);c.request('GET','/',headers={'Host':'attacker.test'});r=c.getresponse();assert r.status==403;r.read();c.close()
        c=http.client.HTTPConnection('127.0.0.1',server.port,timeout=3);c.request('GET','/events');r=c.getresponse();assert r.status==200
        lines=[r.fp.readline().decode() for _ in range(2)];assert lines[0].startswith('id: 1');assert 'example' in lines[1];c.close()
    finally:server.close();store.close()


def test_server_rejects_public_bind(tmp_path):
    store=Store(tmp_path/'db')
    try:
        with pytest.raises(ValueError):Server(store,'0.0.0.0')
    finally:store.close()


def evidence(root):
    p=root/'evidence/scan-one';p.mkdir(parents=True)
    Image.new('RGB',(20,20),'white').save(p/'viewport.png')
    atomic_json(p/'scan.json',{'test':True});atomic_json(p/'snapshot.json',{'nodes':[]})
    atomic_json(p/'manifest.json',{'schema':'testwins.live-evidence/v1','sha256':{x.name:file_digest(x) for x in p.iterdir()}})
    return p


def test_export_dedupes_cells_and_copies_proof(tmp_path):
    root=tmp_path/'live';s=Store(root/'db');e=evidence(root)
    f={'rule':'TW-TEXT-OVERLAP','title':'T','message':'M','selectors':['#x'],'severity':'high','candidate':False}
    r={'findings':[f],'covered_rules':[f['rule']],'status':'complete','evidence':'evidence/scan-one'}
    try:
        for tid in ['site:home:chromium:mobile','site:home:firefox:desktop']:
            for _ in range(2):s.record(tid,'s',r)
        out=tmp_path/'export';info=export(s,root,out,'project')
        assert info['proposals']==1
        proposals=json.loads((out/'proposals.json').read_text());assert 'needs-human' in proposals[0]['labels']
        assert (out/'evidence/scan-one/viewport.png').is_file()
    finally:s.close()


def test_export_tampered_evidence_fails(tmp_path):
    root=tmp_path/'live';s=Store(root/'db');e=evidence(root);(e/'scan.json').write_text('tamper')
    f={'rule':'TW-TEXT-OVERLAP','title':'T','message':'M','selectors':['#x'],'severity':'high','candidate':False}
    try:
        for _ in range(2):s.record('s:p:b:d','scope',{'findings':[f],'covered_rules':[f['rule']],'status':'complete','evidence':'evidence/scan-one'})
        with pytest.raises(ValueError):export(s,root,tmp_path/'export','project')
    finally:s.close()


def test_native_masks_before_persisting_and_flags_change(tmp_path):
    cfg=WatchConfig('native',[],tmp_path/'live',tmp_path,llm={'enabled':False})
    t=Target('s:screen:native:region','s','desktop://s','screen',kind='desktop',region={'left':0,'top':0,'width':200,'height':100},mask_rects=({'x':0,'y':0,'width':80,'height':30},))
    images=[Image.new('RGB',(200,100),'white'),Image.new('RGB',(200,100),'black')]
    scanner=NativeScanner(cfg,capture=lambda _:images.pop(0))
    async def run():
        one=await scanner.scan(t);two=await scanner.scan(t)
        assert Image.open(cfg.output/one['evidence']/'viewport.png').getpixel((5,5))==(35,35,35)
        assert two['findings'][0]['candidate'] is True;assert two['status']=='partial'
    asyncio.run(run())


def import_installer():
    spec=importlib.util.spec_from_file_location('wup_installer',ROOT/'integrations/wup/install.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def wup_fixture(tmp_path):
    root=tmp_path/'wup-checkout';(root/'wup').mkdir(parents=True)
    (root/'wup/cli.py').write_text('import typer\nfrom rich.console import Console\napp = typer.Typer()\nconsole = Console()\n\ndef main():\n    app()\n')
    return root


def test_wup_installer_dry_run_apply_idempotent(tmp_path):
    m=import_installer();root=wup_fixture(tmp_path)
    assert len(m.install(root)['files'])==2;assert not (root/'wup/gui_testwins.py').exists()
    assert m.install(root,True)['mode']=='apply';assert m.install(root,True)['idempotent']
    assert (root/'.testwins-integration-backup/wup/cli.py').exists()


def test_wup_installer_no_overwrite(tmp_path):
    m=import_installer();root=wup_fixture(tmp_path);(root/'wup/gui_testwins.py').write_text('# user work')
    with pytest.raises(ValueError):m.install(root,True)
    assert 'gui_app' not in (root/'wup/cli.py').read_text()


def test_wup_typer_adapter_has_watch_status_export_capacity():
    from typer.testing import CliRunner
    spec=importlib.util.spec_from_file_location('wup_gui',ROOT/'integrations/wup/overlay/wup/gui_testwins.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    r=CliRunner().invoke(m.app,['--help']);assert r.exit_code==0
    for cmd in ['watch','status','export','capacity']:assert cmd in r.stdout
