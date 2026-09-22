#!/usr/bin/env python3
"""Local release tooling. Does not publish, push repositories, or bypass system/browser policy."""
from __future__ import annotations
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERSION=tomllib.loads((ROOT/'pyproject.toml').read_text())['project']['version']


def call(argv,**kwargs):
    return subprocess.run([str(x) for x in argv],cwd=ROOT,check=True,**kwargs)


def sync_profiles():
    source=ROOT/'integrations/clonerd';target=ROOT/'testwins/resources/clonerd'
    if target.exists():shutil.rmtree(target)
    shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','artifacts','.auth','.env','*.pyc'))


def package():
    sync_profiles()
    call([sys.executable,'tools/manage.py','build'])
    dist=ROOT/'dist';archive=dist/f'testwins-{VERSION}-final.zip'
    artifacts=[dist/f'testwins-{VERSION}-py3-none-any.whl',dist/f'testwins-{VERSION}.tar.gz']
    if not all(p.is_file() for p in artifacts):raise RuntimeError('Expected distributions not created')
    excluded={'.git','.venv','.auth','.testwins','.pytest_cache','__pycache__','artifacts','baselines','build','dist',
              '.testwins-live-secret','.testwins-integration-backup'}
    selected=[]
    for p in sorted(ROOT.rglob('*')):
        rel=p.relative_to(ROOT)
        if any(part in excluded or part.endswith('.egg-info') for part in rel.parts):continue
        if not p.is_file() or p.is_symlink() or p.suffix in ('.pyc','.pyo'):continue
        if p.name=='.env' or p.name.startswith('.env.') and p.name!='.env.example':continue
        if p.name.endswith('.storage-state.json'):continue
        # Large screenshots are supplied separately, not repeated in the source release.
        if rel.parts[0]=='verification' and ('landing-runs' in rel.parts or 'release-browser' in rel.parts or 'browser-runs' in rel.parts):continue
        selected.append(p)
    selected+=artifacts
    inventory=[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in selected]
    manifest={'schema':'testwins.release-manifest/v1','version':VERSION,'authority':'none','files':inventory,
              'source':'consolidated user-delivered releases and local changes','published_to_pypi':False,
              'note':'Hashes detect accidental changes; not a cryptographic publisher signature. External dependencies/browser images are not bundled.'}
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in selected:z.write(p,'testwins/'+p.relative_to(ROOT).as_posix())
        z.writestr('testwins/RELEASE-MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for e in inventory:assert hashlib.sha256(z.read('testwins/'+e['path'])).hexdigest()==e['sha256']
    lines=[hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name for p in artifacts+[archive]]
    (dist/'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'archive':str(archive),'files':len(inventory),'verified_archive_hashes':True,'published':False},indent=2))


def main():
    action=sys.argv[1]
    if action=='bootstrap':
        venv=ROOT/'.venv'
        if not venv.exists():call([sys.executable,'-m','venv',venv])
        python=venv/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        call([python,'-m','pip','install','-e','.[live,terminal,dev]'])
        call([python,'-m','playwright','install','chromium'])
        print('Activate .venv, then run make test / make landing-check. TestQL and vision extras are optional explicit installs.')
    elif action=='check':
        sync_profiles()
        call([sys.executable,'-m','compileall','-q','testwins','tools'])
        call([sys.executable,'-m','pytest','-q','-m','not browser','--junitxml=verification/unit-tests.xml'])
        call([sys.executable,'-m','pytest','-q','-m','browser','--junitxml=verification/browser-tests.xml'])
        call([sys.executable,'tools/verify_testql.py'])
        print('Local test gates completed. Docker matrices and upstream WUP still require their integration jobs.')
    elif action in ('clonerd-init','clonerd-check'):
        workspace=Path(os.environ.get('WORKSPACE') or str(ROOT/'.testwins/clonerd')).expanduser().absolute()
        if not workspace.exists():
            call([sys.executable,'-m','testwins','init',workspace,'--profile','clonerd'])
        elif not (workspace/'scope.json').is_file():raise ValueError('Refusing to use an unrelated existing workspace')
        env=dict(os.environ);env['PYTHONPATH']=str(ROOT)
        call([sys.executable,workspace/'tools/manage.py','configure','--url',os.environ.get('CLONERD_URL') or 'http://127.0.0.1:8891'],env=env)
        call([sys.executable,workspace/'tools/manage.py','validate'],env=env)
        if action=='clonerd-check':call([sys.executable,'-m','testwins','suite','--file',workspace/'personas.suite.yaml','--output',workspace/'artifacts/personas'])
        print(workspace)
    elif action=='package-final':package()
    elif action=='sync-profiles':sync_profiles()
    else:raise ValueError('Unknown release command')

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,RuntimeError,subprocess.SubprocessError) as exc:
        print('release:',exc,file=sys.stderr);raise SystemExit(2)
