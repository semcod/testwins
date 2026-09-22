#!/usr/bin/env python3
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from lab import settings
ROOT=Path(__file__).resolve().parents[1]

def main():
    action=sys.argv[1];d=settings();ref=d.get('TESTQL_REF','main')
    if not re.fullmatch(r'[a-zA-Z0-9_.\/-]+',ref):raise ValueError('Invalid TESTQL_REF')
    if action in ('install','install-testql-source'):
        if action=='install':
            extras=d.get('EXTRAS','live,terminal,dev')
            if not re.fullmatch('[a-z,]+',extras):raise ValueError('Invalid EXTRAS')
            subprocess.run([sys.executable,'-m','pip','install','-e',f'.[{extras}]'],cwd=ROOT,check=True)
        if action=='install':return
        subprocess.run([sys.executable,'-m','pip','install','--upgrade',f'git+https://github.com/autogrammar/testql.git@{ref}'],cwd=ROOT,check=True)
        subprocess.run([sys.executable,'-c','from testql.verification import VerificationRequest,run_verification; print("TestQL public API ready")'],check=True)
    elif action=='worker-build':
        subprocess.run(['docker','build','-f','docker/worker.Dockerfile','--build-arg','TESTQL_REF='+ref,'-t','testwins-worker:local','.'],cwd=ROOT,check=True)
    elif action=='build':
        # Avoid stale modules or interpreter caches leaking from a previous wheel build.
        stale=ROOT/'build'
        if stale.is_symlink():raise ValueError('Refusing a symlinked build directory')
        if stale.exists():shutil.rmtree(stale)
        # PEP 517 frontend when installed; offline fallback uses the same backend.
        try:import build
        except ImportError:
            from setuptools import build_meta
            os.chdir(ROOT);(ROOT/'dist').mkdir(exist_ok=True)
            build_meta.build_sdist('dist');build_meta.build_wheel('dist')
        else:subprocess.run([sys.executable,'-m','build'],cwd=ROOT,check=True)
    else:raise ValueError('Unknown management action')

if __name__=='__main__':main()
