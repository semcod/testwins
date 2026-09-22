"""Makefile launcher. Paths are passed as argv data, never interpolated into shell commands."""
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
name=sys.argv[1];cfg=(os.environ.get('WATCH_CONFIG') or 'configs/live/landing.watch.yaml')
root=(os.environ.get('PROJECT_ROOT') or str(ROOT));output=os.environ.get('LIVE_OUTPUT')
if name in {'live-watch','live-once','live-landing'}:
    if name=='live-landing':subprocess.run(['docker','compose','-f',str(ROOT/'landing/compose.yaml'),'up','--build','-d'],check=True)
    args=[sys.executable,'-m','testwins','watch','--config',cfg,'--root',root]
    if output:args+=['--output',output]
    args+=['--once'] if name=='live-once' else ['--serve']
    raise SystemExit(subprocess.call(args,cwd=ROOT))
if name=='live-install':raise SystemExit(subprocess.call([sys.executable,'-m','pip','install','-e',str(ROOT)+'[live]']))
if name in {'live-docker','live-docker-down'}:
    action=['up','--build','-d'] if name=='live-docker' else ['down']
    raise SystemExit(subprocess.call(['docker','compose','-f',str(ROOT/'compose.live.yaml'),*action]))
if name in {'live-novnc','live-novnc-down'}:
    secret=ROOT/'.testwins-live-secret';secret.mkdir(mode=0o700,exist_ok=True)
    os.chmod(secret,0o700)
    password=secret/'vnc_password'
    if not password.exists():
        import secrets
        password.write_text(secrets.token_urlsafe(18));os.chmod(password,0o444)
    action=['up','--build','-d'] if name=='live-novnc' else ['down']
    raise SystemExit(subprocess.call(['docker','compose','-f',str(ROOT/'compose.live.yaml'),'-f',str(ROOT/'compose.live-novnc.yaml'),*action]))
if name=='wup-integrate':
    root=os.environ.get('WUP_ROOT')
    if not root:raise SystemExit('Set WUP_ROOT to the WUP checkout')
    args=[sys.executable,str(ROOT/'integrations/wup/install.py'),root]
    if os.environ.get('APPLY')=='1':args+=['--apply']
    raise SystemExit(subprocess.call(args))
raise SystemExit('Unknown live action')
