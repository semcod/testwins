#!/usr/bin/env python3
"""Build the standalone landing Dockerfile and test it with the installed Python package."""
import argparse
import json
import shutil
from pathlib import Path
import lab
ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['check','up','down']);a=p.parse_args()
    d=lab.settings();d['INSTANCE']='landing';state=lab.state_dir(d)
    if a.action=='down':lab.compose(state,'down','--remove-orphans');return 0
    lab.docker_ready()
    d.update(APP=str(ROOT/'landing/static'),APP_COMMAND='python -m http.server 8080 --bind 0.0.0.0',
             APP_IMAGE='python:3.12-slim',CONFIG=str(ROOT/'landing/tests/audit.yaml'))
    d.setdefault('MATRIX','cdp')
    state=lab.prepare(d);config=json.loads((state/'compose.json').read_text())
    sut=config['services']['sut']
    sut.update(build={'context':str(ROOT/'landing')},image='testwins-landing:local',user='101:101',
               read_only=True,tmpfs=['/tmp:rw,nosuid,size=67108864,mode=1777','/var/cache/nginx','/var/run'],
               working_dir='/usr/share/nginx/html',ports=['127.0.0.1:8090:8080'])
    package=state/'scenario-project';package.mkdir(exist_ok=True)
    if (package/'tests').exists():shutil.rmtree(package/'tests')
    shutil.copytree(ROOT/'landing/tests',package/'tests')
    config['services']['lab']['volumes'].append(lab.bind(package,'/scenario-project'))
    (state/'compose.json').write_text(json.dumps(config,indent=2)+'\n')
    lab.compose(state,'build');lab.compose(state,'up','-d')
    info=json.loads((state/'state.json').read_text());lab.wait_target(state,info,120)
    print('Landing: http://127.0.0.1:8090 | noVNC: http://127.0.0.1:'+str(info['vnc_port'])+'/vnc.html')
    if a.action=='up':return 0
    visual=lab.audit(state,d)
    scenario=lab.compose(state,'exec','-T','lab','python','-m','testwins','task',
        '--file','/scenario-project/tests/scenario.yaml','--project','/scenario-project',
        '--trusted-local','--output','/artifacts/testql',check=False).returncode
    print('Audit exit:',visual,'TestQL exit:',scenario,'(trusted-local is inside the isolated lab container)')
    return max(visual,scenario)

if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError,RuntimeError) as exc:print('landing:',exc);raise SystemExit(2)
