"""Release regression tests: strict gate, storage boundaries, download and API contracts."""
import asyncio
import copy
import hashlib
import json
import os
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
import pytest
import yaml
from testwins.config import load,validate
from testwins.contracts import validate_expectation
from testwins.gate import evaluate,plan_checks
from testwins.downloads import inspect_download
from testwins.sessions import load_state,save_private,state_for
from testwins.performance import measure
from testwins.reporting import finalize


def step(kind='text'):
    return {'id':'test','action':'assert','expect':{'kind':kind,'selector':'#value','value':'ok'}}


def report(status='passed'):
    return {'schema':'testwins.report/v1','cells':[{'id':'chromium-desktop','complete':True}], 'cell_plan':['chromium-desktop'],
        'check_plan':[{'cell':'chromium-desktop','repeat':1,'scene':'flow','step':'test'}],
        'checks':[{'cell':'chromium-desktop','repeat':1,'scene':'flow','step':'test','status':status}],
        'coverage':{'state':'complete'},'summary':{'confirmed':0},'snapshots':[],'run_gaps':[]}

@pytest.mark.parametrize('state,code',[('passed',0),('failed',1),('not_run',2),('blocked',2),('invalid',2)])
def test_gate_strict(state,code):assert evaluate(report(state))['exit_code']==code

@pytest.mark.parametrize('mutation',[
 lambda r:r['checks'].clear(),lambda r:r.pop('check_plan'),lambda r:r['check_plan'].append(r['check_plan'][0]),
 lambda r:r['cells'].clear(),lambda r:r['cell_plan'].clear(),lambda r:r.pop('cell_plan'),
 lambda r:r['checks'].append(r['checks'][0]),lambda r:r['checks'][0].update(step='unknown'),
 lambda r:r['cells'][0].update(complete=False),lambda r:r['run_gaps'].append({'kind':'timeout'})])
def test_gate_missing_work_is_not_green(mutation):
    r=report();mutation(r);assert evaluate(r)['exit_code']==2


def test_gate_failure_ignores_visual_confidence():
    r=report('failed');r['summary']={'confirmed':0,'candidate':1};assert evaluate(r)['exit_code']==1


def test_gate_performance_fail():
    r=report();r['snapshots']=[{'performance':{'status':'failed'}}];assert evaluate(r)['exit_code']==1


def test_plan_is_created_for_all_cells_and_repeats():
    cfg=load();scenes=[{'id':'flow','steps':[step(),{**step(),'id':'second'}]}]
    assert len(plan_checks(cfg,scenes,['a','b','c']))==12

@pytest.mark.parametrize('spec',[
 {'kind':'contains_text','selector':'#x','value':'ok'}, {'kind':'focused','selector':'#x'},
 {'kind':'enabled','selector':'#x'}, {'kind':'disabled','selector':'#x'},
 {'kind':'checked','selector':'#x'}, {'kind':'unchecked','selector':'#x'},
 {'kind':'attribute','selector':'#x','name':'aria-expanded','value':'true'},
 {'kind':'count_min','selector':'li','value':1},
 {'kind':'download','filename_regex':r'.*\.txt','starts_with_hex':'4142'}])
def test_new_contracts_validate(spec):validate_expectation(spec)

@pytest.mark.parametrize('spec',[
 {'kind':'download','filename_regex':'[bad'}, {'kind':'attribute','selector':'#x','value':'true'},
 {'kind':'enabled','selector':'#x','sha256':'bad'}, {'kind':'count_min','selector':'li','value':-1},
 {'kind':'download','filename_regex':'.*','sha256':'bad'}, {'kind':'download','filename_regex':'.*','starts_with_hex':'XX'},
 {'kind':'download','filename_regex':'.*','min_bytes':20,'max_bytes':10}])
def test_bad_contracts_rejected(spec):
    with pytest.raises((ValueError,TypeError)):validate_expectation(spec)


def test_config_goto_same_origin():
    c=load();c['journeys']=[{'id':'flow','path':'/','steps':[{'id':'go','action':'goto','value':'/account','allow_mutation':True,'expect':{'kind':'url','value':'account'}}]}]
    validate(c);c['journeys'][0]['steps'][0]['value']='https://not-authorized.invalid'
    with pytest.raises(ValueError):validate(c)


def test_download_requires_optin():
    c=load();c['journeys']=[{'id':'flow','path':'/','steps':[{'id':'get','action':'download','selector':'#link','allow_mutation':True,'expect':{'kind':'download','filename_regex':r'.*\.txt'}}]}]
    with pytest.raises(ValueError,match='enabled'):validate(c)
    c['downloads']['enabled']=True;validate(c)


def state_doc():return {'cookies':[],'origins':[{'origin':'http://sut:8080','localStorage':[{'name':'auth','value':'SENSITIVE_TEST_VALUE'}]}]}


def test_session_private_and_confined_to_allowlist(tmp_path):
    p=tmp_path/'state.json';save_private(p,state_doc())
    assert load_state(p,load())==state_doc()
    assert 'SENSITIVE_TEST_VALUE' not in str(p)
    if os.name=='posix':assert p.stat().st_mode & 0o077==0
    with pytest.raises(FileExistsError):save_private(p,{})


def test_session_bad_origin_rejected(tmp_path):
    p=tmp_path/'state.json';d=state_doc();d['origins'][0]['origin']='https://external.invalid';save_private(p,d)
    with pytest.raises(ValueError,match='allowlisted'):load_state(p,load())


def test_session_broad_cookie_domain_rejected(tmp_path):
    p=tmp_path/'state.json';save_private(p,{'cookies':[{'domain':'.example.com'}],'origins':[]})
    with pytest.raises(ValueError):load_state(p,load())


def test_session_resolved_relative_to_yaml(tmp_path):
    p=tmp_path/'audit.yaml';p.write_text('sessions:\n  user:\n    storage_state: .auth/user.json\ndefault_session: user\n')
    c=load(p);assert c['sessions']['user']['storage_state']==str(tmp_path/'.auth/user.json')

@pytest.mark.skipif(os.name!='posix',reason='POSIX mode boundary')
def test_world_readable_session_rejected(tmp_path):
    p=tmp_path/'state';p.write_text('{}');p.chmod(0o644)
    with pytest.raises(ValueError,match='0600'):load_state(p,load())


def test_session_symlink_rejected(tmp_path):
    p=tmp_path/'state';save_private(p,{});q=tmp_path/'alias';q.symlink_to(p)
    with pytest.raises(ValueError):load_state(q,load())


class Download:
    def __init__(self,p,name='sample.txt'):self.p=p;self.suggested_filename=name;self.deleted=False
    async def path(self):return self.p
    async def failure(self):return None
    async def delete(self):self.deleted=True


def test_download_default_does_not_retain(tmp_path):
    p=tmp_path/'source';p.write_bytes(b'AB-data');d=Download(p)
    r=asyncio.run(inspect_download(d,{'filename_regex':r'sample\.txt','starts_with_hex':'4142'},{'max_bytes':100,'retain':False},tmp_path/'output'))
    assert r['status']=='passed' and not r['retained'] and d.deleted
    assert not (tmp_path/'output/payload.bin').exists()
    assert 'sample.txt' not in (tmp_path/'output/download.json').read_text()

@pytest.mark.parametrize('change',[{'filename_regex':'wrong'}, {'sha256':'f'*64},{'starts_with_hex':'4242'},{'min_bytes':20},{'max_bytes':1}])
def test_download_rejects_wrong_payload(tmp_path,change):
    p=tmp_path/'source';p.write_bytes(b'AB-data');d=Download(p)
    with pytest.raises(AssertionError):asyncio.run(inspect_download(d,{'filename_regex':r'sample\.txt',**change},{'max_bytes':100,'retain':False},tmp_path/'out'))
    assert d.deleted and json.loads((tmp_path/'out/download.json').read_text())['status']=='failed'


def test_download_retention_does_not_trust_filename(tmp_path):
    p=tmp_path/'source';p.write_bytes(b'ok');d=Download(p,'../../escape')
    r=asyncio.run(inspect_download(d,{'filename_regex':r'.*'},{'max_bytes':100,'retain':True},tmp_path/'out'))
    assert r['retained'] and (tmp_path/'out/payload.bin').read_bytes()==b'ok'
    assert not (tmp_path/'escape').exists()


def test_metrics_required_without_cdp():
    assert asyncio.run(measure(None,{'enabled':True,'required':True,'budgets':{'Nodes':500}}))['status']=='incomplete'


def test_metrics_real_contract_with_stub_transport():
    class CDP:
        async def send(self,*args):return {'metrics':[{'name':'Nodes','value':51}]}
    r=asyncio.run(measure(CDP(),{'enabled':True,'required':True,'budgets':{'Nodes':50}}));assert r['status']=='failed'


def test_report_single_failed_check_is_visible_in_manifest_junit(tmp_path):
    c=load();c.update(matrix='chromium',routes=[],journeys=[{'id':'flow','path':'/','steps':[step()]}])
    c['devices']={'desktop':c['devices']['desktop']};c['capture']['repeats']=1
    r=report('failed');r.update(run_id='unit',schema='testwins.report/v1',created='2026-09-22',project='p',tool_version='0.4.0',config_hash='a'*64,matrix='chromium',environment={},occurrences=[])
    r['cells'][0].update(browser='chromium',device='desktop',version='stub',transport='cdp',errors=[],observed_scenes=1,expected_scenes=1)
    finalize(tmp_path,r,c)
    assert r['gate']['exit_code']==1 and r['cells'][0]['status']=='failed'
    assert json.loads((tmp_path/'manifest.json').read_text())['assessment']=='failed'
    assert 'Mandatory assertion failed' in (tmp_path/'junit.xml').read_text()
    assert 'failed' in (tmp_path/'index.html').read_text()

@pytest.fixture
def api_server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path=='/redirect':
                self.send_response(302);self.send_header('Location','http://never-follow.invalid/');self.end_headers();return
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
            self.wfile.write(b'{"schema":"fixture/v1","status":"ok","secret":"PRIVATE_RESPONSE"}')
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield f'http://127.0.0.1:{server.server_port}'
    finally:server.shutdown();thread.join();server.server_close()


def api_config(tmp_path,url,path='/',status=200):
    cfg={'schema':'testwins.api/v1','id':'fixture','base_url':url,'requests':[{'id':'health','path':path,'expect':{'status':status,'json_equals':{'/schema':'fixture/v1'}}}]}
    p=tmp_path/'api.yaml';p.write_text(yaml.safe_dump(cfg));return p,cfg


def test_api_actual_http_and_redaction(tmp_path,api_server):
    from testwins.api_contracts import run
    p,_=api_config(tmp_path,api_server);root=run(p,tmp_path/'out')
    text=(root/'report.json').read_text();r=json.loads(text)
    assert r['exit_code']==0 and r['checks'][0]['response_status']==200
    assert 'PRIVATE_RESPONSE' not in text


def test_api_mismatch_fails(tmp_path,api_server):
    from testwins.api_contracts import run
    p,_=api_config(tmp_path,api_server,status=201);root=run(p,tmp_path/'out')
    assert json.loads((root/'report.json').read_text())['exit_code']==1


def test_api_does_not_follow_redirect(tmp_path,api_server):
    from testwins.api_contracts import run
    p,cfg=api_config(tmp_path,api_server,path='/redirect');cfg['requests'][0]['expect']={'status':302};p.write_text(yaml.safe_dump(cfg))
    root=run(p,tmp_path/'out');assert json.loads((root/'report.json').read_text())['exit_code']==0


def test_api_mutation_requires_cli_approval(tmp_path,api_server):
    from testwins.api_contracts import run
    p,c=api_config(tmp_path,api_server);c['requests'][0].update(method='POST',allow_mutation=True);p.write_text(yaml.safe_dump(c))
    with pytest.raises(ValueError,match='approve-mutations'):run(p,tmp_path/'out')


def test_api_cross_origin_rejected(tmp_path,api_server):
    from testwins.api_contracts import load as load_api
    p,c=api_config(tmp_path,api_server);c['requests'][0]['path']='http://external.invalid/';p.write_text(yaml.safe_dump(c))
    with pytest.raises(ValueError):load_api(p)


def test_json_pointer_arrays_escaped_keys():
    from testwins.api_contracts import pointer
    assert pointer({'a/b':[{'~x':7}]},'/a~1b/0/~0x')==7
    with pytest.raises(KeyError):pointer([1,2],'/-1')


def test_auth_files_are_excluded_from_staging(tmp_path):
    from testwins.staging import stage
    source=tmp_path/'app';source.mkdir();(source/'.auth').mkdir()
    (source/'.auth/user.json').write_text('PRIVATE_AUTH');(source/'user.storage-state.json').write_text('PRIVATE_AUTH')
    (source/'app.py').write_text('print("safe")')
    output=tmp_path/'out';result=stage(source,output)
    assert result['files']==1 and not (output/'.auth').exists()


def test_api_array_predicates_are_not_silently_ignored(tmp_path,api_server):
    from testwins.api_contracts import run
    p,c=api_config(tmp_path,api_server);c['requests'][0]['expect']['json_min_length']={'/status':5}
    p.write_text(yaml.safe_dump(c));root=run(p,tmp_path/'out')
    assert json.loads((root/'report.json').read_text())['exit_code']==1


def test_suite_uses_strict_report_gate(tmp_path,monkeypatch):
    from testwins.suite import run_suite
    import testwins.runner
    (tmp_path/'audit.yaml').write_text('matrix: chromium\n')
    suite=tmp_path/'suite.yaml';suite.write_text('schema: testwins.suite/v1\nid: gate\nsteps:\n  - id: ui\n    kind: web\n    config: audit.yaml\n')
    async def controlled_run(cfg,output):
        directory=output/'controlled';directory.mkdir(parents=True)
        r=report('failed');r['gate']=evaluate(r)
        (directory/'report.json').write_text(json.dumps(r));return directory
    monkeypatch.setattr(testwins.runner,'run',controlled_run)
    root=run_suite(suite,tmp_path/'output')
    assert json.loads((root/'suite.json').read_text())['status']=='failed'


def test_pytest_bridge_rejects_failed_mandatory_assertion(tmp_path):
    from testwins.pytest_plugin import testwins_assert_report
    verify=testwins_assert_report.__wrapped__()
    p=tmp_path/'report.json';p.write_text(json.dumps(report('failed')))
    with pytest.raises(AssertionError):verify(p)
    p.write_text(json.dumps(report()))
    assert verify(p)['schema']=='testwins.report/v1'


def test_packaged_profiles_validate_and_preserve_all_personas():
    from importlib.resources import files
    root=Path(str(files('testwins').joinpath('resources')))
    assert load(root/'minimal/audit.yaml')['matrix']=='chromium'
    large=load(root/'clonerd/journeys/personas.large.yaml')
    small=load(root/'clonerd/journeys/personas.mobile.yaml')
    assert len(large['journeys'])==len(small['journeys'])==6
    assert {j['id'] for j in large['journeys']}=={j['id'] for j in small['journeys']}
    assert len(large['devices'])==2 and len(small['devices'])==1
