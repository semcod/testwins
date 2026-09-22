#!/usr/bin/env python3
"""Real Chromium/CDP regression fixture. --offline-fixture is explicitly a rendering-only fallback.
It does NOT test HTTP navigation or Docker; no browser/system policy is disabled.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from testwins.config import load
from testwins.runner import run
from testwins.verification import verify_run
from playwright.async_api import Page
ROOT=Path(__file__).resolve().parents[1]


def inspect(root: Path) -> dict:
    result=verify_run(root);r=json.loads((root/'report.json').read_text('utf-8'))
    assert r['coverage']['expected_cells']==3,r['coverage']
    assert r['coverage']['incomplete_cells']==0,r['cells']
    rules={f['rule'] for f in r['findings']}
    required={'TW-TEXT-OVERLAP','TW-TEXT-CLIPPED','TW-CONTROL-OCCLUDED','TW-ALIGNMENT',
              'TW-IMAGE-BROKEN','TW-FUNCTION-ASSERTION','TW-TARGET-SMALL','TW-VIEWPORT-OVERFLOW'}
    assert required<=rules,required-rules
    for finding in r['findings']:
        if finding['rule']=='TW-TEXT-CLIPPED':assert '#legit-ellipsis' not in finding['selectors']
        if finding['rule']=='TW-TEXT-OVERLAP':assert not any('#good-pair' in s for s in finding['selectors'])
    assert all(c['status']=='passed' for c in r['checks'] if c['scene']=='dialog'),r['checks']
    assert all(c['status']=='failed' for c in r['checks'] if c['scene']=='cart')
    for file in root.rglob('*'):
        if file.is_file() and file.suffix in ('.json','.jsonl','.html','.md','.csv','.xml'):
            assert b'SYNTHETIC_SECRET_123' not in file.read_bytes(),file
    return {'valid':True,'scope':'three viewport profiles through real Chromium CDP; two repeats; explicit working and broken UI journeys',
            'fixture_mode':r['environment']['fixture_mode'],'coverage':r['coverage'],'summary':r['summary'],
            'detected_rule_types':sorted(rules),'integrity':result,'environment':r['environment'],
            'browser_versions':sorted({c['version'] for c in r['cells']}),'snapshots':len(r['snapshots']),
            'checks':len(r['checks']),'not_verified':['Docker build and noVNC','Chrome/Edge/Brave and Firefox/WebKit matrix',
            'axe-core (explicitly disabled in this local fixture)','actual Planfile SDK writes','remote vision calls','upstream wellmanifest checker']}


def main() -> int:
    p=argparse.ArgumentParser();p.add_argument('--offline-fixture',action='store_true')
    p.add_argument('--chromium-executable',default=os.environ.get('CHROMIUM_EXECUTABLE') or shutil.which('chromium'))
    p.add_argument('--output',type=Path,default=ROOT/'verification'/'browser-runs');a=p.parse_args()
    cfg=load(ROOT/'configs/demo.yaml',matrix='chromium',headless=True)
    if a.chromium_executable:cfg['executables']['chromium']=a.chromium_executable
    cfg['axe']['enabled']=False;cfg['capture']['timeout_ms']=2500;cfg['capture']['max_cell_seconds']=180
    cfg['capture']['scroll_tiles']=4
    server=None
    try:
        if a.offline_fixture:
            os.environ['TW_VERIFICATION_FIXTURE']='offline-rendered-html-no-http-navigation'
            markup=(ROOT/'examples/buggy-app/index.html').read_text('utf-8')
            async def offline(page,url,**kwargs):
                if url.rstrip('/')!='http://sut:8080':raise ValueError('Offline fixture supports only its single synthetic route')
                await page.set_content(markup,wait_until='domcontentloaded');return None
            with patch.object(Page,'goto',offline):out=asyncio.run(run(cfg,a.output))
        else:
            os.environ['TW_VERIFICATION_FIXTURE']='local-http-fixture'
            with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            cfg['base_url']=f'http://127.0.0.1:{port}'
            server=subprocess.Popen([sys.executable,str(ROOT/'examples/buggy-app/app.py'),'--host','127.0.0.1','--port',str(port)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            for _ in range(50):
                try:
                    with socket.create_connection(('127.0.0.1',port),timeout=.2):break
                except OSError:time.sleep(.1)
            out=asyncio.run(run(cfg,a.output))
        print('Run:',out,flush=True)
        result=inspect(out);(a.output/'verification-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    finally:
        os.environ.pop('TW_VERIFICATION_FIXTURE',None)
        if server:server.terminate();server.wait(timeout=5)
if __name__=='__main__':raise SystemExit(main())
