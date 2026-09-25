"""Copy the explicitly selected application to a disposable build context; never inspect its semantics.
Secrets and developer caches are excluded. Symlinks are rejected, not followed.
"""
from __future__ import annotations
import hashlib
import os
import shutil
import stat
from pathlib import Path

EXCLUDED={'.git','.planfile','.subactor','.testwins','.venv','venv','node_modules','__pycache__','.pytest_cache',
          '.auth','.testwins-auth','.ssh','.aws','.config','.gnupg','artifacts','verification','baselines','build','dist','.npmrc','.pypirc','.netrc'}
SECRET_SUFFIXES={'.pem','.key','.p12','.pfx','.kdbx'}

def stage(source: Path, destination: Path, *, max_bytes: int=512*1024*1024, max_files: int=50000) -> dict:
    source=source.expanduser().resolve(strict=True);destination=destination.resolve()
    if not source.is_dir():raise ValueError('APP must be a directory')
    if source==Path(source.anchor) or source==Path.home().resolve():raise ValueError('Select an application directory, not / or your home directory')
    if destination==source or source.is_relative_to(destination):raise ValueError('Staging destination must not contain the source')
    if destination.exists():shutil.rmtree(destination)
    destination.mkdir(parents=True)
    count=total=0;manifest=[]
    for current,dirs,files in os.walk(source,followlinks=False):
        cur=Path(current)
        # Staging paths inside the lab project are explicitly pruned, including a custom destination.
        dirs[:]=sorted(d for d in dirs if d not in EXCLUDED and not d.endswith('.egg-info') and not (cur/d).resolve().is_relative_to(destination))
        for name in dirs+files:
            p=cur/name
            if p.is_symlink():raise ValueError('Symlinks are not staged: '+str(p.relative_to(source)))
        for name in sorted(files):
            if name in EXCLUDED or name=='.env' or name.startswith('.env.') or name.endswith('.storage-state.json') or Path(name).suffix.lower() in SECRET_SUFFIXES:continue
            p=cur/name;st=p.stat()
            if not stat.S_ISREG(st.st_mode):raise ValueError('Non-regular application file: '+name)
            count+=1;total+=st.st_size
            if count>max_files or total>max_bytes:raise ValueError('Application staging limit exceeded; use a narrower folder or prebuilt image')
            rel=p.relative_to(source);target=destination/rel;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(p,target);target.chmod(0o755 if st.st_mode&0o111 else 0o644)
            manifest.append({'path':rel.as_posix(),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'bytes':st.st_size})
    return {'files':count,'bytes':total,'entries':manifest,'policy':'selected folder; secret patterns and caches excluded; symlinks rejected'}
