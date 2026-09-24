import copy

import pytest

from testwins.config import load, validate
from testwins.overlays import assess_overlays
from testwins.observation import assess_stability

CONTRACT = {'id':'language', 'trigger':'#trigger', 'overlay':'#menu', 'background':['#background']}


@pytest.mark.parametrize('change', [
    {'id':'bad id'}, {'background':[]}, {'background':['']}, {'background':'button'},
    {'trigger':None}, {'overlay':4}, {'unknown':True},
])
def test_rejects_invalid_overlay_contract(change):
    cfg=load();cfg['overlays']=[dict(CONTRACT, **change)]
    with pytest.raises(ValueError): validate(cfg)


def test_duplicate_contract_ids_and_budget():
    cfg=load();cfg['overlays']=[CONTRACT, CONTRACT]
    with pytest.raises(ValueError): validate(cfg)
    cfg['overlays']=[dict(CONTRACT,id=f'o{i}') for i in range(17)]
    with pytest.raises(ValueError): validate(cfg)


def test_missing_collector_evidence_fails_closed():
    snapshot={}
    findings,allowed=assess_overlays(snapshot, {'overlays':[CONTRACT]})
    assert findings[0]['rule']=='TW-OVERLAY-CONTRACT'
    assert not allowed
    assert snapshot['gaps'][0]['kind']=='overlay_contract'


def test_relationship_changes_invalidate_stability():
    before={'nodes':[], 'texts':[], 'overlays':[{'id':'language','state':'active'}]}
    after=copy.deepcopy(before);after['overlays'][0]['state']='invalid'
    assert assess_stability(before,after)['state'] is False


def test_report_keeps_intentional_coverage_separate_from_violations():
    from testwins.reporting import overlay_text
    report={'overlay_observations':[
        {'state':'active','stable':True,'coverage':[{},{}]},
        {'state':'active','stable':False,'coverage':[{}]},
        {'state':'invalid','stable':True,'coverage':[]}]}
    text=overlay_text(report)
    assert '2 stable control-coverage observations' in text
    assert '1 invalid relationships' in text
