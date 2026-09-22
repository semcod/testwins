"""Sequential, bounded orchestration; a web observation scope is distinct from execution tasks."""
from __future__ import annotations
import asyncio
import json
import uuid
from pathlib import Path
import yaml
from .util import confined, atomic_json, utc_now, file_digest
from .tasks import load_task, run_task


def run_suite(path: Path, output: Path, *, trusted_local: bool=False, image: str='testwins-worker:local',network: str='none') -> Path:
    spec=yaml.safe_load(path.read_text('utf-8'));base=path.resolve().parent
    if not isinstance(spec,dict) or set(spec)!={'schema','id','steps'} or spec['schema']!='testwins.suite/v1':
        raise ValueError('Invalid suite')
    steps=spec['steps']
    if not isinstance(steps,list) or not 1<=len(steps)<=30:raise ValueError('Suite requires 1..30 steps')
    # Validate the complete shape before starting any execution.
    for step in steps:
        if not isinstance(step,dict) or set(step)-{'id','kind','config','project','url','matrix'} or step.get('kind') not in {'web','task','api'}:
            raise ValueError('Invalid suite step')
        confined(base,step['config']).resolve(strict=True)
        if step['kind']=='task':confined(base,step.get('project','.')).resolve(strict=True)
    root=output.resolve()/('suite-'+utc_now().replace(':','').replace('.','-')+'-'+uuid.uuid4().hex[:6]);root.mkdir(parents=True)
    results=[]
    for step in steps:
        try:
            if step['kind']=='web':
                from .config import load
                from .runner import run
                cfg=load(confined(base,step['config']),base_url=step.get('url'),matrix=step.get('matrix'))
                run_dir=asyncio.run(run(cfg,root/'web'));report=json.loads((run_dir/'report.json').read_text())
                status=report['gate']['status']
            elif step['kind']=='api':
                from .api_contracts import run as run_api
                run_dir=run_api(confined(base,step['config']),root/'api')
                status=json.loads((run_dir/'report.json').read_text())['status']
            else:
                run_dir=run_task(load_task(confined(base,step['config'])),confined(base,step.get('project','.')),root/'tasks',trusted_local=trusted_local,image=image,network=network)
                status=json.loads((run_dir/'result.json').read_text())['status']
            results.append({'id':step['id'],'kind':step['kind'],'status':status,'directory':str(run_dir.relative_to(root))})
        except Exception as exc:
            results.append({'id':step['id'],'kind':step['kind'],'status':'incomplete','exception_type':type(exc).__name__})
    statuses={r['status'] for r in results}
    status='incomplete' if 'incomplete' in statuses else 'failed' if 'failed' in statuses else 'validated' if statuses=={'validated'} else 'incomplete' if 'validated' in statuses else 'passed'
    atomic_json(root/'suite.json',{'schema':'testwins.suite-result/v1','id':spec['id'],'status':status,
                'config_sha256':file_digest(path),'results':results,'note':'Validated scenarios were not executed.'})
    return root
