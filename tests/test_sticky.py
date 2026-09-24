import copy

import pytest

from testwins.config import load, validate
from testwins.observation import assess_stability
from testwins.sticky import assess_sticky_regions, scoped_regions

CONTRACT = {'id': 'toolbar', 'selector': '#toolbar', 'content': '#content'}


@pytest.mark.parametrize('change', [
    {'id': '../x'}, {'content': ''}, {'selector': None}, {'frame': 'unknown'},
    {'frame': None}, {'ignore_headings': True},
])
def test_invalid_sticky_config_cannot_authorize_coverage(change):
    cfg = load(); cfg['sticky_regions'] = [dict(CONTRACT, **change)]
    with pytest.raises(ValueError): validate(cfg)


def test_contract_ids_and_count_are_bounded():
    cfg = load(); cfg['sticky_regions'] = [CONTRACT, CONTRACT]
    with pytest.raises(ValueError): validate(cfg)
    cfg['sticky_regions'] = [dict(CONTRACT, id=f'x{i}') for i in range(17)]
    with pytest.raises(ValueError): validate(cfg)


def test_scope_and_missing_evidence_fail_closed():
    cfg = load(); cfg['frames'] = [{'id': 'guide', 'selector': 'iframe'}]
    cfg['sticky_regions'] = [CONTRACT, dict(CONTRACT, id='child', frame='guide')]
    validate(cfg)
    assert scoped_regions(cfg, {'kind': 'root'}) == [CONTRACT]
    snap = {'scope': {'kind': 'frame', 'id': 'guide'}}
    findings, hidden = assess_sticky_regions(snap, cfg)
    assert not hidden and findings[0]['rule'] == 'TW-STICKY-CONTRACT'
    assert snap['gaps'][0]['contract'] == 'child'


def test_evidence_changes_invalidate_observation():
    before = {'nodes': [], 'texts': [], 'sticky_regions': [{'id': 'toolbar', 'state': 'active', 'coverage': [1]}]}
    after = copy.deepcopy(before); after['sticky_regions'][0]['coverage'] = []
    assert assess_stability(before, after)['state'] is False


def test_unstable_or_mismatched_range_is_never_hidden():
    text = {'selector': '#old', 'rect': {'x': 0}, 'protectedFromSticky': False}
    evidence = dict(CONTRACT, state='active', coverage=[{'text_index': 0, 'selector': '#old', 'rect': {'x': 0}, 'hit_samples': 5}])
    snap = {'texts': [text], 'sticky_regions': [evidence], 'stable': False}
    assert assess_sticky_regions(snap, {'sticky_regions': [CONTRACT]})[1] == set()
    snap['stable'] = True; text['rect'] = {'x': 1}
    assert assess_sticky_regions(snap, {'sticky_regions': [CONTRACT]})[1] == set()


def test_report_exposes_coverage_separately():
    from testwins.reporting import sticky_text
    text = sticky_text({'sticky_observations': [
        {'state': 'active', 'stable': True, 'coverage': [{}, {}]},
        {'state': 'active', 'stable': False, 'coverage': [{}]},
        {'state': 'invalid', 'stable': True, 'coverage': []}]})
    assert '2 stable text-range observations' in text and '1 unverified' in text
