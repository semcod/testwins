import json
from pathlib import Path
from testwins.config import load
from testwins.reporting import finalize

def data():
    return {'schema':'testwins.report/v1','run_id':'fixture','created':'2026-09-22T00:00:00Z','project':'p','tool_version':'0.1.0',
            'config_hash':'a'*64,'matrix':'chromium','environment':{},'snapshots':[],'occurrences':[],'checks':[],'run_gaps':[],
            'cells':[{'id':'chromium-desktop','browser':'chromium','device':'desktop','transport':'cdp','version':None,
                      'errors':[{'code':'TW-BROWSER-UNAVAILABLE'}],'observed_scenes':0,'expected_scenes':2}]}

def test_missing_browser_never_passes(tmp_path):
    r=data();finalize(tmp_path,r,load())
    assert r['coverage']['state']=='incomplete'
    assert r['cells'][0]['status']=='incomplete'
    assert '<error ' in (tmp_path/'junit.xml').read_text()
    assert json.loads((tmp_path/'manifest.json').read_text())['assessment']=='incomplete'

def test_bounded_crawl_error_not_full_coverage(tmp_path):
    r=data();r['cells'][0].update(errors=[],observed_scenes=2)
    r['run_gaps']=[{'kind':'crawl_failure'}];finalize(tmp_path,r,load())
    assert r['coverage']['state']=='incomplete'


def test_single_unverified_overlay_cannot_pass_without_repeatable_findings(tmp_path):
    from testwins.overlays import assess_overlays
    cfg=load();cfg['overlays']=[{'id':'menu','trigger':'#trigger','overlay':'#menu','background':['#behind']}]
    snapshot={}
    findings,allowed=assess_overlays(snapshot,cfg)
    assert findings and not allowed
    r=data();r['cells'][0].update(errors=[],observed_scenes=2)
    r['snapshots']=[{'meta':{'browser':'chromium','device':'desktop'},'gaps':snapshot['gaps']}]
    finalize(tmp_path,r,cfg)
    assert r['summary']['confirmed']==0
    assert r['gate']['status']=='incomplete'
    assert json.loads((tmp_path/'manifest.json').read_text())['assessment']=='incomplete'
