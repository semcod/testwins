from pathlib import Path
import pytest
from stage import stage
from lab import dotenv,prepare

def test_excludes_secrets_and_caches(tmp_path):
    source=tmp_path/'app with spaces';source.mkdir()
    for name in ('index.html','.env','.env.prod','credential.pem','.npmrc'):(source/name).write_text('content')
    (source/'node_modules').mkdir();(source/'node_modules'/'x').write_text('dependency')
    result=stage(source,tmp_path/'copy');assert result['files']==1
    assert (tmp_path/'copy'/'index.html').exists();assert not (tmp_path/'copy'/'.env').exists()

def test_symlinks_rejected(tmp_path):
    source=tmp_path/'app';source.mkdir();(source/'file').symlink_to('/etc/passwd')
    with pytest.raises(ValueError,match='Symlink'):stage(source,tmp_path/'copy')

def test_size_limit(tmp_path):
    source=tmp_path/'app';source.mkdir();(source/'file').write_text('abc')
    with pytest.raises(ValueError,match='limit'):stage(source,tmp_path/'copy',max_bytes=2)

def test_dotenv_no_command_substitution(tmp_path):
    p=tmp_path/'.env';p.write_text('APP_COMMAND="$(touch /tmp/must-not-exist)"\n# example\n')
    assert dotenv(p)['APP_COMMAND']=='$(touch /tmp/must-not-exist)'
