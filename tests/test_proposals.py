from types import SimpleNamespace
import json
import pytest
from testwins.proposals import validate_producer,publish


def proposal(candidate=False):
    return {'schema':'planfile.ticket-proposal.v1','proposal_id':'testwins:1','dedupe_key':'project:1','name':'UI issue','description':'Observed evidence','priority':'high',
            'source':{'tool':'testwins','tool_version':'0.1.0','finding_id':'1','artifact_digest':'a'*64},
            'labels':['testwins-candidate' if candidate else 'testwins-confirmed'],'files':[],'acceptance_criteria':['verify UI'],'evidence_refs':[]}

# Adapter doubles, NOT a substitute for claiming a real Planfile integration test.
class ContractDouble:
    @staticmethod
    def model_validate(p):
        validate_producer(p)
        class Value:
            proposal_id=p['proposal_id'];dedupe_key=p['dedupe_key']
            def to_ticket_kwargs(self):return {k:p[k] for k in ('name','description','priority','labels','files','acceptance_criteria','source')}
        return Value()
class StoreDouble:
    def __init__(self):self.items={};self.calls=[]
    def create_ticket_deduplicated(self,**kw):
        self.calls.append(kw);key=kw['dedupe_key'];created=key not in self.items
        if created:self.items[key]=SimpleNamespace(id='PLF-001')
        return self.items[key],created

def bundle(tmp_path,p=None):
    file=tmp_path/'proposals.json';file.write_text(json.dumps([p or proposal()]));return file

@pytest.mark.parametrize('field',['executor','queue','sprint','capabilities','approval','uri','transport'])
def test_no_authority_fields(field):
    p=proposal();p[field]='execute'
    with pytest.raises(ValueError):validate_producer(p)

def test_dry_run_no_sdk_or_mutations(tmp_path):
    p=bundle(tmp_path);before=list(tmp_path.iterdir());r=publish(p,tmp_path)
    assert r['selected']==1 and r['mode']=='dry-run';assert list(tmp_path.iterdir())==before

def test_candidate_not_published_by_default(tmp_path):assert publish(bundle(tmp_path,proposal(True)),tmp_path)['selected']==0

def test_no_auto_ready_candidates(tmp_path):
    with pytest.raises(ValueError):publish(bundle(tmp_path,proposal(True)),tmp_path,include_candidates=True,ready=True)

def test_adapter_uses_atomic_api_and_review_gate(tmp_path):
    store=StoreDouble();p=bundle(tmp_path)
    a=publish(p,tmp_path,apply=True,backend=store,proposal_type=ContractDouble)
    b=publish(p,tmp_path,apply=True,backend=store,proposal_type=ContractDouble)
    assert a['receipts'][0]['created'] and not b['receipts'][0]['created']
    assert store.calls[0]['executor'] is None and 'needs-human' in store.calls[0]['labels']

def test_invalid_bundle_never_mutates(tmp_path):
    store=StoreDouble();p=bundle(tmp_path);bad=proposal();bad['executor']='shell';p.write_text(json.dumps([proposal(),bad]))
    with pytest.raises(ValueError):publish(p,tmp_path,apply=True,backend=store,proposal_type=ContractDouble)
    assert not store.calls


def test_publication_paginates_eligible_findings(tmp_path):
    rows=[]
    for i in range(5):
        p=proposal(candidate=i==1);p['proposal_id']=f'testwins:{i}';p['dedupe_key']=f'project:{i}';rows.append(p)
    path=tmp_path/'many.json';path.write_text(json.dumps(rows))
    first=publish(path,tmp_path,limit=2)
    assert first['eligible_total']==4 and first['next_offset']==2
    assert first['proposal_ids']==['testwins:0','testwins:2']
    last=publish(path,tmp_path,limit=2,offset=2)
    assert last['proposal_ids']==['testwins:3','testwins:4'] and last['next_offset'] is None


def test_publication_offset_out_of_range_is_empty(tmp_path):
    r=publish(bundle(tmp_path),tmp_path,offset=20)
    assert r['selected']==0 and r['next_offset'] is None


@pytest.mark.parametrize('offset',[-1,True,1.5])
def test_publication_rejects_invalid_offset(tmp_path,offset):
    with pytest.raises(ValueError):publish(bundle(tmp_path),tmp_path,offset=offset)
