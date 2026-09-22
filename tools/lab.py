#!/usr/bin/env python3
"""Host orchestration: only Python stdlib + Docker Compose v2. No host desktop dependency."""
from __future__ import annotations
import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path
from stage import stage
ROOT=Path(__file__).resolve().parents[1]


def dotenv(path: Path) -> dict[str,str]:
    result={}
    if not path.is_file():return result
    for n,line in enumerate(path.read_text('utf-8').splitlines(),1):
        line=line.strip()
        if not line or line.startswith('#'):continue
        if '=' not in line:raise ValueError(f'Invalid .env line {n}')
        k,v=line.split('=',1);k=k.strip();v=v.strip()
        if not re.fullmatch(r'[A-Z][A-Z0-9_]*',k):raise ValueError(f'Invalid .env key at line {n}')
        if len(v)>=2 and v[0]==v[-1] and v[0] in "\"'":v=v[1:-1]
        result[k]=v  # Deliberately no eval, substitutions, expansion, or shell execution.
    return result


def settings() -> dict[str,str]:
    d=dotenv(ROOT/'.env');d.update({k:v for k,v in os.environ.items() if v})
    return d


def invoke(args: list[str], *, capture: bool=False, check: bool=True, **kwargs):
    return subprocess.run(args,cwd=ROOT,check=check,text=True,capture_output=capture,**kwargs)


def state_dir(d: dict) -> Path:
    name=d.get('INSTANCE','lab')
    if not re.fullmatch(r'[a-z][a-z0-9_-]{0,35}',name):raise ValueError('INSTANCE must be a safe lowercase id')
    return ROOT/'.testwins'/name


def compose(state: Path, *args: str, **kwargs):
    cmd=['docker','compose','--project-name','testwins-'+state.name,'--file',str(state/'compose.json')]
    if (state/'state.json').is_file():
        override=json.loads((state/'state.json').read_text()).get('compose_override')
        if override:cmd+=['--file',override]
    return invoke([*cmd,*args],**kwargs)


def docker_ready() -> None:
    if not shutil.which('docker'):raise RuntimeError('Docker is not installed. Install Docker Engine/Desktop with Compose v2.')
    invoke(['docker','compose','version'],capture=True)
    invoke(['docker','info'],capture=True)


def bind(source: Path, target: str, readonly: bool=True) -> dict:
    return {'type':'bind','source':str(source.resolve()),'target':target,'read_only':readonly}


def port(d,key,default):
    value=int(d.get(key,default))
    if not 1024<=value<=65535:raise ValueError(key+' must be in [1024,65535]')
    return value


def prepare(d: dict, *, demo: bool=False) -> Path:
    state=state_dir(d);state.mkdir(parents=True,exist_ok=True)
    matrix=d.get('MATRIX','cdp')
    if matrix not in ('cdp','engines','chromium'):raise ValueError('Unknown MATRIX')
    if demo:
        source=ROOT/'examples/buggy-app';image='python:3.12-slim';install=''
        command='python app.py --host 0.0.0.0 --port 8080';app_port=8080;config=ROOT/'configs/demo.yaml'
    else:
        if not d.get('APP') or not d.get('APP_COMMAND'):
            raise ValueError('Set APP=/absolute/application/folder and APP_COMMAND="server command binding 0.0.0.0"')
        source=Path(d['APP']);image=d.get('APP_IMAGE','python:3.12-slim');install=d.get('APP_INSTALL','')
        command=d['APP_COMMAND'];app_port=port(d,'APP_PORT','8080');config=Path(d.get('CONFIG',str(ROOT/'configs/audit.yaml')))
    if not re.fullmatch(r'[A-Za-z0-9_./:@-]+',image):raise ValueError('Invalid base image reference')
    uid=int(d.get('LAB_UID',str(os.getuid() if hasattr(os,'getuid') and os.getuid()!=0 else 1000)))
    gid=int(d.get('LAB_GID',str(os.getgid() if hasattr(os,'getgid') and os.getgid()!=0 else 1000)))
    if uid<=0 or gid<=0:raise ValueError('Lab and application must not run as root')
    source=source.expanduser().resolve(strict=True);config=config.expanduser().resolve(strict=True)
    context=state/'target-build';context.mkdir(exist_ok=True)
    source_manifest=stage(source,context/'app')
    (state/'source-manifest.json').write_text(json.dumps(source_manifest,indent=2)+'\n')
    target_dockerfile=(f'FROM {image}\nUSER root\nWORKDIR /workspace\n'
                       f'COPY --chown={uid}:{gid} app/ /workspace/\n'
                       f'RUN mkdir -p /home/testwins && chown -R {uid}:{gid} /workspace /home/testwins\n'
                       f'USER {uid}:{gid}\nENV HOME=/home/testwins\nENV PATH=/home/testwins/.local/bin:${{PATH}}\n')
    if install:target_dockerfile+='RUN '+json.dumps(['/bin/sh','-lc',install])+'\n'
    target_dockerfile+='ENTRYPOINT []\nCMD '+json.dumps(['/bin/sh','-lc','mkdir -p "$HOME"; '+command])+'\n'
    (context/'Dockerfile').write_text(target_dockerfile,'utf-8')
    shutil.copyfile(config,state/'audit.yaml')
    password=state/'vnc-password'
    if not password.exists():password.write_text(secrets.token_hex(4)+'\n') # VNC protocol password is 8 characters.
    password.chmod(0o600)
    artifacts=ROOT/'artifacts'/state.name;artifacts.mkdir(parents=True,exist_ok=True)
    baselines=ROOT/'baselines';baselines.mkdir(exist_ok=True)
    # On native Linux prepare writable bind directories for the non-root containers.
    if hasattr(os,'getuid') and os.getuid()==0:
        for directory in (artifacts,baselines):os.chown(directory,uid,gid)
        os.chown(password,uid,gid)
    private_network=d.get('APP_ALLOW_NETWORK','0')!='1'
    common={'init':True,'cap_drop':['ALL'],'security_opt':['no-new-privileges:true'],
            'pids_limit':512,'networks':['audit'],'user':f'{uid}:{gid}'}
    services={
        'sut':{**common,'build':{'context':str(context)},'image':'testwins-sut-'+state.name+':local',
               'expose':[str(app_port)],'environment':{'HOME':'/home/testwins'},
               'mem_limit':d.get('APP_MEMORY','2g'),'cpus':d.get('APP_CPUS','2'),
               'tmpfs':['/tmp:rw,nosuid,size=536870912,mode=1777'],
               'working_dir':'/workspace'},
        'lab':{**common,'build':{'context':str(ROOT),'dockerfile':'docker/Dockerfile','target':'cdp' if matrix=='cdp' else 'engines','args':{'TESTQL_REF':d.get('TESTQL_REF') or 'main'}},
               'image':'testwins-'+matrix+':local','read_only':True,'shm_size':'2gb',
               'mem_limit':d.get('LAB_MEMORY','6g'),'cpus':d.get('LAB_CPUS','4'),
               'environment':{'HOME':'/tmp/testwins-home','DISPLAY':':99','PLAYWRIGHT_BROWSERS_PATH':'/ms-playwright'},
               'ports':[f"127.0.0.1:{port(d,'VNC_PORT','6080')}:6080",f"127.0.0.1:{port(d,'REPORT_PORT','8088')}:8088"],
               'volumes':[bind(state/'audit.yaml','/config/audit.yaml'),bind(artifacts,'/artifacts',False),
                          bind(baselines,'/baselines'),bind(password,'/run/secrets/vnc_password')],
               'tmpfs':['/tmp:rw,nosuid,size=2147483648,mode=1777'],
               'depends_on':['sut']}}
    if d.get('AUTH_DIR'):
        directory=Path(d['AUTH_DIR']).expanduser()
        if directory.is_symlink() or not directory.is_dir():raise ValueError('AUTH_DIR must be an explicit regular directory')
        # Private state is a read-only runtime input, never a build context or SUT volume.
        services['lab']['volumes'].append(bind(directory.resolve(),'/auth'))
    if matrix=='cdp':
        # Brand browser packages are Linux amd64; the target service can use its native architecture.
        services['lab']['platform']='linux/amd64'
    env_file=d.get('SUT_ENV_FILE')
    if env_file:
        # Explicit target-only test secrets, never controller's .env.
        services['sut']['env_file']=[str(Path(env_file).expanduser().resolve(strict=True))]
    document={'services':services,'networks':{'audit':{'internal':private_network}}}
    (state/'compose.json').write_text(json.dumps(document,indent=2)+'\n')
    info={'matrix':matrix,'app_port':app_port,'base_url':f'http://sut:{app_port}',
          'artifacts':str(artifacts),'uid':uid,'gid':gid,'config':str(config),'app':str(source),
          'vnc_port':port(d,'VNC_PORT','6080'),'report_port':port(d,'REPORT_PORT','8088'),
          'runtime_egress':'blocked' if private_network else 'operator-enabled',
          'compose_override':str(Path(d['COMPOSE_OVERRIDE']).expanduser().resolve(strict=True)) if d.get('COMPOSE_OVERRIDE') else None}
    (state/'state.json').write_text(json.dumps(info,indent=2)+'\n')
    return state


def wait_target(state: Path, info: dict, seconds: int) -> None:
    # Infrastructure TCP readiness only; not a source of UI bug findings.
    code='import socket; s=socket.create_connection(("sut",'+str(info['app_port'])+'),timeout=2); s.close()'
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        if compose(state,'exec','-T','lab','python','-c',code,check=False,capture=True).returncode==0:return
        time.sleep(1)
    raise RuntimeError('Target did not open its internal TCP port. Check make logs and bind the service to 0.0.0.0.')


def audit(state: Path, d: dict) -> int:
    info=json.loads((state/'state.json').read_text())
    wait_target(state,info,int(d.get('STARTUP_TIMEOUT','120')))
    result=compose(state,'exec','-T','lab','python','-m','testwins','run','--config','/config/audit.yaml',
                   '--url',info['base_url'],'--matrix',info['matrix'],'--output','/artifacts',check=False)
    print(f"Reports: http://127.0.0.1:{info['report_port']}/  | noVNC: http://127.0.0.1:{info['vnc_port']}/vnc.html")
    return result.returncode


def latest(state: Path) -> Path:
    info=json.loads((state/'state.json').read_text());root=Path(info['artifacts'])
    pointer=json.loads((root/'latest.json').read_text());rel=pointer['directory']
    path=(root/rel).resolve()
    if not path.is_relative_to(root.resolve()):raise ValueError('Unsafe latest run pointer')
    return path


def main() -> int:
    p=argparse.ArgumentParser();p.add_argument('action',choices=['up','check','demo','audit','down','logs','status','report','doctor','prepare','publish','vnc-password'])
    a=p.parse_args();d=settings();state=state_dir(d)
    try:
        if a.action=='doctor':
            print('Python:',sys.version.split()[0]);print('Docker:',shutil.which('docker') or 'MISSING');docker_ready();return 0
        if a.action=='prepare':
            state=prepare(d,demo=d.get('DEMO')=='1');print(state/'compose.json');return 0
        if a.action in ('up','demo','check'):
            docker_ready();state=prepare(d,demo=a.action=='demo')
            compose(state,'build');compose(state,'up','-d')
            info=json.loads((state/'state.json').read_text());wait_target(state,info,int(d.get('STARTUP_TIMEOUT','120')))
            print(f"noVNC: http://127.0.0.1:{info['vnc_port']}/vnc.html ; password: make vnc-password")
            if a.action in ('demo','check'):
                rc=audit(state,d)
                if a.action=='check':return rc
                if rc==1:print('Demo completed: expected seeded UI violations were found.');return 0
                if rc==0:raise RuntimeError('Demo unexpectedly found no repeatable seeded defects')
                return rc
            return 0
        if a.action=='audit':return audit(state,d)
        if a.action=='down':compose(state,'down','--remove-orphans');return 0
        if a.action=='logs':return compose(state,'logs','--tail','100',check=False).returncode
        if a.action=='status':return compose(state,'ps',check=False).returncode
        if a.action=='vnc-password':print((state/'vnc-password').read_text().strip());return 0
        if a.action=='report':
            run=latest(state);info=json.loads((state/'state.json').read_text());print(f"http://127.0.0.1:{info['report_port']}/{run.name}/index.html");return 0
        if a.action=='publish':
            run=latest(state);project=Path(d.get('PLANFILE_PROJECT','')).expanduser().resolve()
            if not d.get('PLANFILE_PROJECT') or not (project/'.planfile').is_dir():raise ValueError('PLANFILE_PROJECT must contain an initialized .planfile directory')
            apply=d.get('APPLY','0')=='1';info=json.loads((state/'state.json').read_text());ref=d.get('PLANFILE_REF','main')
            if not re.fullmatch(r'[A-Za-z0-9_./-]+',ref):raise ValueError('Invalid PLANFILE_REF')
            if apply:
                print('Publisher SDK ref:',ref,'(pin a reviewed commit SHA for reproducibility)')
                invoke(['docker','build','-f','docker/publisher.Dockerfile','--build-arg','PLANFILE_REF='+ref,'-t','testwins-publisher:local','.'])
            image='testwins-publisher:local' if apply else 'testwins-'+info['matrix']+':local'
            cmd=['docker','run','--rm','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges:true',
                 '--user',f"{info['uid']}:{info['gid']}",'--tmpfs','/tmp:rw,nosuid,size=134217728,mode=1777',
                 '-e','HOME=/tmp','--mount',f'type=bind,src={run},dst=/input,readonly',
                 '--entrypoint','python']
            if apply:cmd+=['--mount',f'type=bind,src={project/".planfile"},dst=/project/.planfile']
            cmd+=[image,'-m','testwins','publish','/input/proposals.json','--project','/project','--limit',d.get('TICKET_LIMIT','25'),'--offset',d.get('TICKET_OFFSET','0')]
            if apply:cmd+=['--apply']
            if d.get('INCLUDE_CANDIDATES')=='1':cmd+=['--include-candidates']
            if d.get('READY')=='1':cmd+=['--ready']
            result=invoke(cmd,capture=True,check=False)
            print(result.stdout,end='');print(result.stderr,end='',file=sys.stderr)
            if result.returncode==0 and apply:
                receipt=state/('publish-'+str(time.time_ns())+'.json');receipt.write_text(result.stdout)
                print('Publication receipt:',receipt)
            return result.returncode
    except (ValueError,OSError,RuntimeError,subprocess.SubprocessError) as exc:
        print('lab:',exc,file=sys.stderr);return 2
    return 0

if __name__=='__main__':raise SystemExit(main())
