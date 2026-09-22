"""Run trusted test definitions inside disposable Docker workers by default."""
from __future__ import annotations
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any
import yaml
from .util import atomic_json, digest, file_digest, utc_now
from .staging import stage

FIELDS = {'schema','id','backend','files','url','dry_run','step_timeout_ms','timeout_seconds','steps',
          'command','args','cwd','max_output_bytes','templates','expected_exit_code'}


def validate_task(task: Any) -> dict:
    if not isinstance(task,dict) or set(task)-FIELDS or task.get('schema')!='testwins.task/v1':
        raise ValueError('Invalid closed testwins.task/v1 document')
    if not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}',task.get('id','')):
        raise ValueError('Task needs a stable lowercase id')
    if task.get('backend') not in {'testql','desktop','terminal'}:
        raise ValueError('Task backend must be testql, desktop or terminal')
    for key,default,low,high in [('timeout_seconds',120,1,3600),('step_timeout_ms',10000,100,60000)]:
        v=task.get(key,default)
        if type(v) is not int or not low<=v<=high: raise ValueError('Invalid '+key)
    if type(task.get('dry_run',False)) is not bool: raise ValueError('dry_run must be boolean')
    if task['backend']=='testql':
        files=task.get('files')
        if not isinstance(files,list) or not files or len(files)>100:
            raise ValueError('Provide 1..100 scenario file specifications')
        for spec in files:
            if not isinstance(spec,str) or Path(spec).is_absolute() or '..' in Path(spec).parts:
                raise ValueError('Scenario specifications must stay inside the selected project')
        if 'url' in task:
            from .util import origin
            origin(task['url'])
    else:
        if not isinstance(task.get('steps'),list) or not 1<=len(task['steps'])<=100:
            raise ValueError('Provide 1..100 explicit steps')
        if task.get('dry_run'): raise ValueError('dry_run is currently supported only for TestQL')
    if 'expected_exit_code' in task and (type(task['expected_exit_code']) is not int or not 0<=task['expected_exit_code']<=255):
        raise ValueError('Invalid expected exit code')
    return task


def load_task(path: Path) -> dict:
    if path.stat().st_size>2_000_000: raise ValueError('Task exceeds size limit')
    return validate_task(yaml.safe_load(path.read_text('utf-8')))


def worker_env() -> dict[str,str]:
    # Do not inherit API keys, cloud tokens or host PYTHONPATH.
    allowed={'PATH','HOME','LANG','LC_ALL','DISPLAY','XAUTHORITY','XDG_RUNTIME_DIR',
             'DBUS_SESSION_BUS_ADDRESS','PLAYWRIGHT_BROWSERS_PATH','SYSTEMROOT','WINDIR'}
    env={k:v for k,v in os.environ.items() if k in allowed}
    env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1')
    return env


def docker_args(image: str, source: Path, request: Path, output: Path, *, name: str,
                network: str='none', display: bool=False) -> list[str]:
    if not re.fullmatch(r'[A-Za-z0-9_./:@-]+',image): raise ValueError('Invalid worker image')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+',network) or network=='host':
        raise ValueError('Use none or an explicit isolated Docker network, never host')
    uid=os.getuid() if hasattr(os,'getuid') and os.getuid()!=0 else 1000
    gid=os.getgid() if hasattr(os,'getgid') and os.getgid()!=0 else 1000
    cmd=['docker','run','--rm','--init','--name',name,'--network',network,
         '--read-only','--cap-drop','ALL','--security-opt','no-new-privileges:true',
         '--pids-limit','256','--memory','3g','--cpus','2','--shm-size','1g',
         '--user',f'{uid}:{gid}','--tmpfs','/tmp:rw,nosuid,size=1073741824,mode=1777',
         '-e','HOME=/tmp/home','-e','PLAYWRIGHT_BROWSERS_PATH=/ms-playwright',
         '--mount',f'type=bind,src={source},dst=/input,readonly',
         '--mount',f'type=bind,src={request},dst=/request.json,readonly',
         '--mount',f'type=bind,src={output},dst=/output',
         '--entrypoint','/usr/local/bin/testwins-worker',image,
         '--request','/request.json','--project','/input','--output','/output']
    return cmd


def run_task(task: dict, project: Path, output: Path, *, trusted_local: bool=False,
             image: str='testwins-worker:local', network: str='none') -> Path:
    task=validate_task(task);project=project.expanduser().resolve(strict=True)
    root=output.resolve()/(utc_now().replace(':','').replace('.','-')+'-'+task['id']+'-'+uuid.uuid4().hex[:6])
    root.mkdir(parents=True,exist_ok=False)
    atomic_json(root/'task.json',task)
    env=worker_env();env['TW_PROJECT_KEY']=digest(str(project))
    name='testwins-'+uuid.uuid4().hex[:12]
    with tempfile.TemporaryDirectory(prefix='testwins-task-') as td:
        tmp=Path(td);source=tmp/'project'
        inventory=stage(project,source)
        atomic_json(root/'source-manifest.json',inventory)
        request=tmp/'request.json';atomic_json(request,task);request.chmod(0o644)
        if trusted_local:
            cmd=[sys.executable,'-m','testwins.task_worker','--request',str(request),'--project',str(source),'--output',str(root)]
        else:
            if not shutil.which('docker'):
                atomic_json(root/'result.json',{'schema':'testwins.task-result/v1','status':'incomplete','reason':'docker_missing'})
                raise RuntimeError('Docker is required. --trusted-local explicitly permits executing trusted scenarios on this host.')
            if hasattr(os,'getuid') and os.getuid()==0:
                os.chown(root,1000,1000)
                # Source parent must be traversable by non-root worker.
                tmp.chmod(0o755)
            cmd=docker_args(image,source,request,root,name=name,network=network)
            cmd[2:2]=['-e','TW_PROJECT_KEY='+digest(str(project))]
        process=subprocess.Popen(cmd,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        try:
            rc=process.wait(timeout=task.get('timeout_seconds',120))
        except subprocess.TimeoutExpired:
            if os.name=='posix':os.killpg(process.pid,signal.SIGKILL)
            else:process.kill()
            process.wait()
            if not trusted_local:
                subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15,check=False)
            rc=124
        if not (root/'result.json').is_file():
            atomic_json(root/'result.json',{'schema':'testwins.task-result/v1','task_id':task['id'],
                        'status':'incomplete','reason':'worker_timeout' if rc==124 else 'worker_failed',
                        'exit_code':rc})
        result=json.loads((root/'result.json').read_text())
        if rc not in (0,1,2) and result.get('status') in ('passed','validated'):
            result.update(status='incomplete',reason='worker_exit_mismatch');atomic_json(root/'result.json',result)
        atomic_json(root/'execution.json',{'isolation':'trusted-local-process' if trusted_local else 'docker',
                    'network':'host' if trusted_local else network,'worker_exit':rc,'source_manifest_sha256':file_digest(root/'source-manifest.json')})
    return root


def exit_code(result: dict) -> int:
    return 0 if result.get('status') in ('passed','validated') else 1 if result.get('status')=='failed' else 2
