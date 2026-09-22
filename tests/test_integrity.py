import json
from pathlib import Path
import pytest
from testwins.events import EventLog,verify
from testwins.util import canonical,confined,digest,redact_url

def ledger(tmp_path):
    (tmp_path/'proof.txt').write_text('proof');l=EventLog(tmp_path,'run-1');l.append('started',input_hash=digest({}),evidence=['proof.txt']);l.append('finished',input_hash=digest({}));return l

def test_hash_chain(tmp_path):ledger(tmp_path);assert verify(tmp_path)['events']==2

def test_evidence_tampering(tmp_path):
    ledger(tmp_path);(tmp_path/'proof.txt').write_text('modified')
    with pytest.raises(ValueError,match='digest'):verify(tmp_path)

def test_log_tampering(tmp_path):
    l=ledger(tmp_path);text=l.path.read_text().replace('testwins.started','testwins.forged');l.path.write_text(text)
    with pytest.raises(ValueError):verify(tmp_path)

def test_no_floating_log_values():
    with pytest.raises(ValueError):canonical({'duration':1.5},integers_only=True)

def test_no_reuse_log(tmp_path):
    ledger(tmp_path)
    with pytest.raises(ValueError):EventLog(tmp_path,'run-1')

@pytest.mark.parametrize('path',['../../etc/passwd','/etc/passwd'])
def test_path_confinement(tmp_path,path):
    with pytest.raises(ValueError):confined(tmp_path,path)

def test_symlink_confinement(tmp_path):
    (tmp_path/'escape').symlink_to('/etc')
    with pytest.raises(ValueError):confined(tmp_path,'escape/passwd')

def test_redacted_url():
    assert '123456' not in redact_url('https://user:pass@example.com/?access_token=123456&page=2')
    assert 'user:pass' not in redact_url('https://user:pass@example.com/')

def test_long_stage_slug_collision_avoided():
    from testwins.util import slug
    assert slug('x'*105+'a')!=slug('x'*105+'b')
    assert len(slug('x'*200))<=100

def test_fragment_token_redacted():
    assert 'MY_SECRET' not in redact_url('https://example.com/#access_token=MY_SECRET')
