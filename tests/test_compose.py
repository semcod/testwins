import json
from pathlib import Path
import lab

def test_isolated_compose_generation(tmp_path,monkeypatch):
    # Build descriptor only; this does not claim an executed Docker integration test.
    root=tmp_path/'lab';root.mkdir();(root/'configs').mkdir();(root/'configs'/'audit.yaml').write_text('schema: testwins.config/v1\n')
    source=tmp_path/'target with spaces';source.mkdir();(source/'app.py').write_text('print("hello")')
    monkeypatch.setattr(lab,'ROOT',root)
    state=lab.prepare({'APP':str(source),'APP_COMMAND':'python app.py','APP_IMAGE':'python:3.12-slim',
                       'LAB_UID':'1000','LAB_GID':'1000','MATRIX':'cdp'})
    d=json.loads((state/'compose.json').read_text());sut=d['services']['sut'];browser=d['services']['lab']
    assert d['networks']['audit']['internal'] is True
    assert sut['user']=='1000:1000' and browser['read_only']
    assert browser['platform']=='linux/amd64' and browser['shm_size']=='2gb'
    assert all(p.startswith('127.0.0.1:') for p in browser['ports'])
    assert 'volumes' not in sut
    assert not any('/target with spaces' in str(v) for v in browser['volumes'])
    assert not any('docker.sock' in str(v) for v in browser['volumes'])
    dockerfile=(state/'target-build'/'Dockerfile').read_text()
    assert 'USER 1000:1000' in dockerfile and 'HOME=/home/testwins' in dockerfile

def test_egress_opt_in_is_explicit(tmp_path,monkeypatch):
    root=tmp_path/'lab';root.mkdir();(root/'configs').mkdir();(root/'configs'/'audit.yaml').write_text('{}')
    app=tmp_path/'app';app.mkdir();(app/'x').write_text('x');monkeypatch.setattr(lab,'ROOT',root)
    state=lab.prepare({'APP':str(app),'APP_COMMAND':'true','APP_ALLOW_NETWORK':'1','MATRIX':'engines'})
    d=json.loads((state/'compose.json').read_text())
    assert d['networks']['audit']['internal'] is False
    assert 'platform' not in d['services']['lab']
