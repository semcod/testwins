from __future__ import annotations
import argparse
import asyncio
import json
import sys
from pathlib import Path
from .config import load, MATRICES
from .util import atomic_json


def parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(prog='testwins',description='Rendered-UI audit lab: screenshots, DOM geometry and explicit UI contracts')
    from . import __version__
    p.add_argument('--version',action='version',version='testwins '+__version__)
    sub=p.add_subparsers(dest='command',required=True)
    r=sub.add_parser('run');r.add_argument('--config',type=Path,default=Path('configs/audit.yaml'))
    r.add_argument('--url');r.add_argument('--matrix',choices=MATRICES);r.add_argument('--output',type=Path,default=Path('artifacts'))
    r.add_argument('--headless',action='store_true',default=None);r.add_argument('--chromium-executable')
    r.add_argument('--no-axe',action='store_true',help='Explicitly remove axe checks from this audit scope')
    v=sub.add_parser('validate');v.add_argument('--config',type=Path,required=True)
    v=sub.add_parser('verify');v.add_argument('run',type=Path)
    b=sub.add_parser('baseline');b.add_argument('run',type=Path);b.add_argument('--directory',type=Path,required=True);b.add_argument('--approve',action='store_true')
    t=sub.add_parser('publish');t.add_argument('proposals',type=Path);t.add_argument('--project',type=Path,required=True)
    t.add_argument('--apply',action='store_true');t.add_argument('--include-candidates',action='store_true');t.add_argument('--ready',action='store_true');t.add_argument('--limit',type=int,default=25);t.add_argument('--offset',type=int,default=0)
    t.add_argument('--receipt',type=Path,help='Write publication receipt outside the immutable input run')
    sub.add_parser('doctor')
    x=sub.add_parser('api',help='Separate explicit HTTP contracts; not a browser matrix')
    x.add_argument('--config',type=Path,required=True);x.add_argument('--output',type=Path,default=Path('artifacts/api'));x.add_argument('--approve-mutations',action='store_true')
    g=sub.add_parser('gate',help='Require every planned assertion; no confidence-based bypass')
    g.add_argument('report',type=Path,help='Run directory (also checks integrity) or report.json')
    g=sub.add_parser('auth-save',help='Open an isolated browser; save private state after a signed-in selector appears')
    g.add_argument('--config',type=Path,required=True);g.add_argument('--output',type=Path,required=True)
    g.add_argument('--ready-selector',required=True);g.add_argument('--timeout-ms',type=int,default=120000)

    i=sub.add_parser('init');i.add_argument('directory',type=Path);i.add_argument('--profile',choices=['minimal','clonerd'],default='minimal')
    for command in ('task','scenario','suite'):
        t=sub.add_parser(command)
        if command=='scenario':
            t.add_argument('files',nargs='+');t.add_argument('--dry-run',action='store_true');t.add_argument('--url',default='http://sut:8080')
        else:t.add_argument('--file',type=Path,required=True)
        t.add_argument('--project',type=Path,default=Path('.'));t.add_argument('--output',type=Path,default=Path('artifacts/tasks'))
        t.add_argument('--trusted-local',action='store_true',help='Explicitly execute reviewed scenarios on this host, without Docker isolation')
        t.add_argument('--image',default='testwins-worker:local');t.add_argument('--network',default='none')
    v=sub.add_parser('vision');v.add_argument('source',type=Path);v.add_argument('--output',type=Path,required=True)
    v.add_argument('--env',type=Path,default=Path('.env'));v.add_argument('--goal',default='');v.add_argument('--before',type=Path);v.add_argument('--regions-json',type=Path)
    c=sub.add_parser('cv');c.add_argument('image',type=Path);c.add_argument('--output',type=Path,required=True)
    c.add_argument('--backend',choices=['opencv','yolo','regions'],default='opencv');c.add_argument('--weights',type=Path)
    c.add_argument('--weights-sha256');c.add_argument('--trust-model',action='store_true');c.add_argument('--regions-json',type=Path)
    d=sub.add_parser('draft');d.add_argument('image',type=Path);d.add_argument('--snapshot',type=Path,required=True)
    d.add_argument('--goal',required=True);d.add_argument('--url',required=True);d.add_argument('--output',type=Path,required=True);d.add_argument('--env',type=Path,default=Path('.env'))
    from .live.cli import register
    register(sub)
    return p


def main(argv: list[str] | None=None) -> int:
    p=parser();a=p.parse_args(argv)
    try:
        if a.command in {'watch','live-status','live-serve','live-export','capacity','diagnose','catalog'}:
            from .live.cli import dispatch
            return dispatch(a)
        if a.command=='api':
            from .api_contracts import run
            root=run(a.config,a.output,approve_mutations=a.approve_mutations)
            report=json.loads((root/'report.json').read_text())
            print(json.dumps({'directory':str(root),'status':report['status'],'checks':len(report['checks'])}));return report['exit_code']
        if a.command=='gate':
            from .gate import evaluate
            if a.report.is_dir():
                from .verification import verify_run
                verify_run(a.report);path=a.report/'report.json'
            else:path=a.report
            result=evaluate(json.loads(path.read_text('utf-8')))
            print(json.dumps(result,indent=2));return result['exit_code']
        if a.command=='auth-save':
            from .sessions import capture_session
            if not 1000<=a.timeout_ms<=600000:raise ValueError('timeout-ms must be 1000..600000')
            asyncio.run(capture_session(load(a.config),a.output,a.ready_selector,a.timeout_ms))
            print(json.dumps({'saved':True,'private_file':str(a.output),'included_in_reports':False}));return 0
        if a.command=='doctor':
            import importlib.metadata, importlib.util, shutil
            from pathlib import Path
            result={'package':'testwins','python':sys.version.split()[0], 'docker':shutil.which('docker'),'packages':{}}
            for name in ('testwins','testql','playwright','litellm','opencv-python-headless','ultralytics','mss','pyautogui','pexpect'):
                try:result['packages'][name]=importlib.metadata.version(name)
                except importlib.metadata.PackageNotFoundError:result['packages'][name]=None
            try:
                from testql.verification import VerificationRequest,run_verification
                result['testql_public_api']=True
            except ImportError:result['testql_public_api']=False
            pw_exe = None
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    pw_exe = p.chromium.executable_path
            except Exception:
                pass
            result['browsers'] = {
                'playwright_chromium': pw_exe if pw_exe and Path(pw_exe).exists() else None,
                'system_chromium': shutil.which('chromium') or shutil.which('chromium-browser'),
                'system_chrome': shutil.which('google-chrome') or shutil.which('google-chrome-stable'),
            }
            result['note']='Optional backends are reported individually; missing SDK never becomes an executed test.'
            print(json.dumps(result,indent=2));return 0
        if a.command=='init':
            import shutil
            from importlib.resources import files
            if a.directory.exists():raise ValueError('Choose a new directory')
            source=files('testwins').joinpath('resources',a.profile)
            shutil.copytree(str(source),a.directory)
            print(str(a.directory));return 0
        if a.command in ('task','scenario','suite'):
            from .tasks import load_task,run_task,exit_code
            if a.command=='suite':
                from .suite import run_suite
                root=run_suite(a.file,a.output,trusted_local=a.trusted_local,image=a.image,network=a.network)
                result=json.loads((root/'suite.json').read_text())
            else:
                task=load_task(a.file) if a.command=='task' else {'schema':'testwins.task/v1','id':'scenario','backend':'testql','files':a.files,'url':a.url,'dry_run':a.dry_run}
                root=run_task(task,a.project,a.output,trusted_local=a.trusted_local,image=a.image,network=a.network)
                result=json.loads((root/'result.json').read_text())
            print(json.dumps({'directory':str(root),'result':result},ensure_ascii=False,indent=2));return exit_code(result)
        if a.command=='cv':
            from .cv import analyze
            result=analyze(a.image,a.output,backend=a.backend,weights=a.weights,trust_model=a.trust_model,expected_sha256=a.weights_sha256,regions_file=a.regions_json)
            print(json.dumps({'output':str(a.output),'regions':len(result['regions']),'defects':0}));return 0
        if a.command=='vision':
            from .llm import review,env_file
            root=review(a.source,a.output,env_file(a.env),goal=a.goal,before=a.before,regions_file=a.regions_json)
            result=json.loads((root/'vision.json').read_text());print(json.dumps({'output':str(root),'status':result['status'],'calls':result['calls']}))
            return 2 if result['status']=='incomplete' else 0
        if a.command=='draft':
            from .llm import Client,Settings,env_file
            from .drafting import draft
            root=draft(a.image,a.snapshot,a.goal,a.url,a.output,Client(Settings.from_env(env_file(a.env))))
            print(json.dumps({'output':str(root),'executed':False,'review_required':True}));return 0
        if a.command=='run':
            from .runner import run
            c=load(a.config,base_url=a.url,matrix=a.matrix,headless=a.headless)
            if a.chromium_executable:c['executables']['chromium']=a.chromium_executable
            if a.no_axe:c['axe']['enabled']=False
            root=asyncio.run(run(c,a.output));r=json.loads((root/'report.json').read_text('utf-8'))
            print(json.dumps({'run':str(root),'coverage':r['coverage'],'summary':r['summary']},ensure_ascii=False,indent=2))
            return r['gate']['exit_code']
        if a.command=='validate':
            load(a.config);result={'valid':True,'config':str(a.config)}
        elif a.command=='verify':
            from .verification import verify_run
            result=verify_run(a.run)
        elif a.command=='baseline':
            from .baseline import approve
            result={'approved_baselines':approve(a.run,a.directory,authorized=a.approve)}
        elif a.command=='publish':
            from .proposals import publish
            result=publish(a.proposals,a.project,apply=a.apply,include_candidates=a.include_candidates,ready=a.ready,limit=a.limit,offset=a.offset)
            if a.receipt:atomic_json(a.receipt,result)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (ValueError,KeyError,TypeError,OSError,ImportError,RuntimeError) as exc:
        # Config/SDK errors, not raw application console output.
        print(f'testwins: {type(exc).__name__}: {exc}',file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
