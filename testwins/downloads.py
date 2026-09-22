"""Validate a completed browser download. Payload retention is explicit and disabled by default."""
from __future__ import annotations
import hashlib
import re
import shutil
from pathlib import Path
from .util import atomic_json


async def inspect_download(download, spec: dict, policy: dict, folder: Path) -> dict:
    record={'schema':'testwins.download/v1','status':'incomplete','retained':False,
            'filename':'[REDACTED]','scope':'filename, byte size, optional prefix and SHA-256; not semantic document correctness'}
    folder.mkdir(parents=True,exist_ok=True)
    try:
        if await download.failure():raise RuntimeError('Browser download failed')
        raw=await download.path()
        if raw is None:raise RuntimeError('Download payload not accessible')
        path=Path(raw);size=path.stat().st_size
        record['bytes']=size
        if size>min(policy['max_bytes'],spec.get('max_bytes',policy['max_bytes'])):
            record['status']='failed';record['reason']='size_limit';raise AssertionError('Download exceeds configured size limit')
        if size<spec.get('min_bytes',1):
            record['status']='failed';record['reason']='too_small';raise AssertionError('Download smaller than required')
        # Use an operator-supplied bounded pattern; never use the suggested name as a path.
        if len(download.suggested_filename)>512 or re.fullmatch(spec['filename_regex'],download.suggested_filename) is None:
            record['status']='failed';record['reason']='filename';raise AssertionError('Unexpected download filename')
        digest=hashlib.sha256()
        with path.open('rb') as stream:
            prefix=stream.read(64);digest.update(prefix)
            for block in iter(lambda:stream.read(65536),b''):digest.update(block)
        record['sha256']=digest.hexdigest()
        if spec.get('sha256') and record['sha256']!=spec['sha256']:
            record['status']='failed';record['reason']='sha256';raise AssertionError('Download SHA-256 mismatch')
        if spec.get('starts_with_hex') and not prefix.startswith(bytes.fromhex(spec['starts_with_hex'])):
            record['status']='failed';record['reason']='prefix';raise AssertionError('Download prefix mismatch')
        if policy['retain']:
            target=folder/'payload.bin'
            with path.open('rb') as source,target.open('xb') as dest:shutil.copyfileobj(source,dest,65536)
            target.chmod(0o600);record.update(retained=True,payload='payload.bin')
        record['status']='passed'
        return record
    finally:
        atomic_json(folder/'download.json',record)
        # Context closure also deletes temporary browser downloads.
        try:await download.delete()
        except Exception:pass
