#!/usr/bin/env python3
"""Preflighted, idempotent installer for an operator-owned WUP checkout. Dry-run by default."""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

INSERT='\n# Optional Testwins GUI monitor; importing does not start scans.\nfrom .gui_testwins import app as gui_app\napp.add_typer(gui_app, name="gui")\n'
ANCHOR='console = Console()\n'


def plan(root:Path):
    root=root.resolve();cli=root/'wup/cli.py';module=root/'wup/gui_testwins.py'
    if not cli.is_file() or cli.is_symlink() or module.is_symlink():raise ValueError('Expected regular wup/cli.py in a WUP checkout')
    old=cli.read_text('utf-8');tree=ast.parse(old)
    if not any(isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='app' for t in n.targets) for n in tree.body):
        raise ValueError('Unknown WUP CLI structure; review patch manually')
    overlay=Path(__file__).parent/'overlay/wup/gui_testwins.py';source=overlay.read_text('utf-8')
    if 'from .gui_testwins import app as gui_app' in old:
        if INSERT not in old or not module.is_file() or module.read_text('utf-8')!=source:
            raise ValueError('Existing integration differs; refusing to overwrite local work')
        return {}
    if old.count(ANCHOR)!=1:raise ValueError('Expected unique console initialization; review upstream changes')
    if module.exists():raise ValueError('wup/gui_testwins.py already exists; refusing to overwrite')
    new=old.replace(ANCHOR,ANCHOR+INSERT,1);ast.parse(new);ast.parse(source)
    return {cli:(old,new),module:(None,source)}


def install(root:Path,apply=False):
    changes=plan(root);result={'mode':'apply' if apply else 'dry-run','files':[str(p.relative_to(root.resolve())) for p in changes],
      'remote_repository_modified':False,'idempotent':not changes}
    if not apply or not changes:return result
    backup=root.resolve()/'.testwins-integration-backup'
    if backup.exists():raise ValueError('Backup already exists; review it before another installation')
    backup.mkdir()
    for p,(old,new) in changes.items():
        if old is not None:
            dest=backup/p.relative_to(root.resolve());dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(old,encoding='utf-8')
    written=[]
    try:
        for p,(old,new) in changes.items():
            fd,temp=tempfile.mkstemp(prefix='.testwins-',dir=p.parent)
            with os.fdopen(fd,'w',encoding='utf-8') as f:f.write(new)
            os.chmod(temp,p.stat().st_mode&0o777 if p.exists() else 0o644)
            os.replace(temp,p);written.append(p)
    except BaseException:
        for p in written:
            old=changes[p][0]
            if old is None:p.unlink(missing_ok=True)
            else:p.write_text(old,encoding='utf-8')
        raise
    (backup/'receipt.json').write_text(json.dumps(result,indent=2))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--apply',action='store_true');a=p.parse_args()
    try:print(json.dumps(install(a.root,a.apply),indent=2))
    except (ValueError,OSError,SyntaxError) as exc:p.exit(2,str(exc)+'\n')
