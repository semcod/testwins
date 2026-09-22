"""Contract tests use explicit fakes. OpenCV and Pexpect tests use actual local libraries."""
from __future__ import annotations
import copy,json,os,sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from PIL import Image,ImageDraw
from testwins.integrations.testql import normalize
from testwins.util import digest,file_digest
from testwins.tasks import validate_task,worker_env,docker_args,exit_code
from testwins.llm import Settings,Client,review_image,validate_response,env_file
from testwins.cv import validate_regions,contours,match_template,yolo,nms,analyze
from testwins.drafting import compile_draft


def payload(*,dry=False,steps=3,executed=3,skipped=0,ok=True,failed=0):
    r=dict(file='test.oql',source='test.oql',ok=ok,passed=steps-failed,failed=failed,steps=steps,
           skipped=skipped,validated=steps if dry else 0,executed=executed,profile=None,duration_ms=1,
           errors=[],warnings=[],failures=[])
    d=dict(schema='testql.verification-result.v1',ok=ok,files=1,passed_files=int(ok),failed_files=int(not ok),runs=[r],dry_run=dry,request_hash='a'*64)
    d['result_hash']=digest(d);return d


def resign(d):
    d.pop('result_hash',None);d['result_hash']=digest(d);return d

@pytest.mark.parametrize('opts,status',[({},'passed'),({'dry':True,'executed':0},'validated'),
    ({'skipped':1,'executed':2},'incomplete'),({'steps':0,'executed':0},'incomplete'),
    ({'executed':0},'incomplete'),({'ok':False,'failed':1},'failed')])
def test_testql_status(opts,status):
    d=payload(**opts);assert normalize(d,'a'*64,dry_run=opts.get('dry',False))['status']==status

@pytest.mark.parametrize('field,value',[('schema','bad'),('request_hash','b'*64),('dry_run',True),('files',2),('passed_files',8),('ok',False)])
def test_testql_rejects_inconsistent_contract(field,value):
    d=payload();d[field]=value;resign(d)
    with pytest.raises(ValueError):normalize(d,'a'*64,dry_run=False)

def test_testql_tamper():
    d=payload();d['runs'][0]['steps']=8
    with pytest.raises(ValueError,match='hash'):normalize(d,'a'*64,dry_run=False)

@pytest.mark.parametrize('v',[-1,True,'1',None])
def test_testql_bad_counter(v):
    d=payload();d['runs'][0]['executed']=v;resign(d)
    with pytest.raises(ValueError):normalize(d,'a'*64,dry_run=False)

def test_testql_no_scenarios_not_green():
    d=payload();d.update(runs=[],files=0,passed_files=0);resign(d)
    assert normalize(d,'a'*64,dry_run=False)['status']=='incomplete'

TASK={'schema':'testwins.task/v1','id':'demo','backend':'testql','files':['tests/*.oql']}
@pytest.mark.parametrize('spec',['/etc/passwd','../tests/a.oql','tests/../../a'])
def test_task_paths(spec):
    with pytest.raises(ValueError):validate_task({**TASK,'files':[spec]})

@pytest.mark.parametrize('extra',[{'timeout_seconds':True},{'timeout_seconds':0},{'timeout_seconds':3601},{'dry_run':'false'},{'shell':'do not execute'},{'backend':'unknown'},{'expected_exit_code':-1}])
def test_task_closed(extra):
    with pytest.raises(ValueError):validate_task({**TASK,**extra})

def test_env_does_not_leak(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY','DO_NOT_LEAK');monkeypatch.setenv('PYTHONPATH','/bad')
    assert 'OPENROUTER_API_KEY' not in worker_env() and 'PYTHONPATH' not in worker_env()

def test_docker_boundary(tmp_path):
    cmd=docker_args('testwins-worker:local',tmp_path,tmp_path/'request',tmp_path/'out',name='test-test')
    assert cmd[cmd.index('--network')+1]=='none' and '--read-only' in cmd
    assert '--privileged' not in cmd and not any('docker.sock' in s for s in cmd)
    assert '--cap-drop' in cmd and '--user' in cmd
    with pytest.raises(ValueError):docker_args('x',tmp_path,tmp_path,tmp_path,name='x',network='host')

@pytest.mark.parametrize('status,code',[('passed',0),('validated',0),('failed',1),('incomplete',2),('other',2)])
def test_status_exit(status,code):assert exit_code({'status':status})==code


def local_settings(**kwargs):
    return Settings.from_env({'LLM_PROVIDER':'ollama','LLM_VISION_MODEL':'fixture-vision','LLM_VISION_CAPABLE':'1',**kwargs})

def fake_response(value):
    return {'choices':[{'message':{'content':json.dumps(value)}}], 'usage':{'total_tokens':12,'private':'secret'}}

def test_provider_selection_one_file(tmp_path,monkeypatch):
    for k in tuple(os.environ):
        if k.startswith(('LLM_','OLLAMA_')):monkeypatch.delenv(k)
    p=tmp_path/'.env';p.write_text('# LLM_PROVIDER=openrouter\nLLM_PROVIDER=ollama\nLLM_VISION_MODEL="fixture-vision"\n')
    s=Settings.from_env(env_file(p));assert s.model=='ollama_chat/fixture-vision' and not s.remote

@pytest.mark.parametrize('extra',[{}, {'LLM_ALLOW_REMOTE':'1'}, {'LLM_ALLOW_REMOTE':'1','LLM_API_KEY':'x','LLM_BASE_URL':'http://provider.invalid/v1'},
 {'LLM_ALLOW_REMOTE':'1','LLM_API_KEY':'x','LLM_BASE_URL':'https://user:pass@provider.invalid/v1'}])
def test_remote_guard(extra):
    with pytest.raises(ValueError):Settings.from_env({'LLM_PROVIDER':'openrouter','LLM_VISION_MODEL':'fixture',**extra})

def test_secret_not_in_repr():
    s=Settings.from_env({'LLM_PROVIDER':'openrouter','LLM_VISION_MODEL':'fixture','LLM_ALLOW_REMOTE':'1','LLM_API_KEY':'SENSITIVE_TEST_KEY'})
    assert s.model=='openrouter/fixture' and 'SENSITIVE_TEST_KEY' not in repr(s)

def test_llm_calls_bounded_and_no_tools():
    calls=[]
    def fn(**kw):calls.append(kw);return fake_response({'ok':True})
    client=Client(local_settings(LLM_MAX_CALLS='1'),completion=fn)
    client.call([{'role':'user','content':'data'}])
    with pytest.raises(RuntimeError,match='budget'):client.call([])
    assert len(calls)==1 and 'tools' not in calls[0] and calls[0]['num_retries']==0
    assert client.usage==[{'total_tokens':12}]

def test_llm_image_capability_gate():
    settings=local_settings();settings.vision_ack=False
    client=Client(settings,completion=lambda **_:fake_response({}),vision_checker=lambda **_:False)
    with pytest.raises(ValueError,match='support'):client.call([])
    assert client.calls==0

def test_llm_errors_redacted():
    def fn(**kw):raise ValueError('SENSITIVE_TEST_KEY')
    with pytest.raises(RuntimeError) as e:Client(local_settings(),completion=fn).call([])
    assert 'SENSITIVE_TEST_KEY' not in str(e.value)

@pytest.fixture
def screenshot(tmp_path):
    p=tmp_path/'screen.png';im=Image.new('RGB',(400,300),'white');d=ImageDraw.Draw(im)
    d.rectangle((30,40,120,100),fill='blue');d.line((35,45,100,90),fill='yellow',width=6)
    im.save(p);return p

def test_vision_before_after_actual_image_encoding(screenshot,tmp_path):
    before=tmp_path/'before.png';Image.new('RGB',(400,300),'black').save(before)
    calls=[]
    def fn(**kw):calls.append(kw);return fake_response({'verdict':'pass','reason':'Synthetic adapter fixture, not an actual LLM judgment','findings':[]})
    out=review_image(screenshot,Client(local_settings(),completion=fn),before=before,goal='fixture')
    parts=calls[0]['messages'][1]['content'];assert len(parts)==3
    assert parts[1]['image_url']['url']!=parts[2]['image_url']['url']
    assert out['status']=='candidate' and out['authority']=='none' and out['human_review_required']
    assert out['before_sha256']==file_digest(before)

@pytest.mark.parametrize('box',[{'x':-1,'y':0,'width':10,'height':10},{'x':0,'y':0,'width':401,'height':10},{'x':0,'y':float('nan'),'width':1,'height':1}])
def test_vision_box_bounds(box):
    f={'category':'alignment','message':'fixture','selectors':[],'boxes':[box]}
    with pytest.raises(ValueError):validate_response({'findings':[f]},set(),400,300)

def test_vision_invented_selector():
    f={'category':'other','message':'fixture','selectors':['#invented'],'boxes':[dict(x=1,y=1,width=10,height=10)]}
    with pytest.raises(ValueError):validate_response({'findings':[f]},{'#real'},400,300)

def test_opencv_actual(screenshot,tmp_path):
    assert len(contours(screenshot))>0
    tpl=tmp_path/'template.png';Image.open(screenshot).crop((25,35,125,105)).save(tpl)
    result=match_template(screenshot,tpl);assert result['found'] and result['score']>.99
    assert result['box']['x']==25 and result['box']['y']==35
    data=analyze(screenshot,tmp_path/'cv.json');assert data['defects']==[] and data['authority']=='none'

def test_uniform_rgb_template_rejected(screenshot,tmp_path):
    tpl=tmp_path/'constant.png';Image.new('RGB',(20,20),(255,0,0)).save(tpl)
    with pytest.raises(ValueError,match='texture'):match_template(screenshot,tpl)

def test_template_larger(screenshot,tmp_path):
    tpl=tmp_path/'large.png';Image.new('RGB',(401,301),'white').save(tpl)
    assert not match_template(screenshot,tpl)['found']

def test_nms_class_aware():
    r=lambda label,score:{'label':label,'score':score,'box':dict(x=0,y=0,width=10,height=10)}
    out=nms([r('button',.9),r('button',.7),r('icon',.8)])
    assert len(out)==2 and out[0]['score']==.9

def test_yolo_mock_adapter_tiles_and_offsets(tmp_path):
    """Fake detections exercise adapter coordinate logic; no weights/model inference are claimed."""
    import numpy as np
    p=tmp_path/'long.png';Image.new('RGB',(400,2000),'white').save(p)
    weights=tmp_path/'fake.pt';weights.write_bytes(b'NOT A MODEL')
    calls=[]
    class Fake:
        def predict(self,**kw):
            calls.append(kw);return [SimpleNamespace(names={0:'button'},boxes=SimpleNamespace(xyxy=np.array([[5,10,45,30]]),conf=np.array([.9]),cls=np.array([0])))]
    out=yolo(p,weights,trust_model=True,expected_sha256=file_digest(weights),factory=lambda *a,**k:Fake())
    assert len(calls)==2 and len(out)==2 and out[1]['box']['y']==730
    assert all(c['save'] is False and c['device']=='cpu' for c in calls)

@pytest.mark.parametrize('kwargs',[{}, {'trust_model':True,'expected_sha256':'wrong'}])
def test_yolo_trust_required(screenshot,tmp_path,kwargs):
    p=tmp_path/'fake.pt';p.write_bytes(b'fixture')
    with pytest.raises(ValueError):yolo(screenshot,p,**kwargs)

@pytest.mark.parametrize('change',[{'score':float('nan')},{'score':2},{'label':''},{'authority':'execute'}])
def test_regions_closed(change):
    r={'label':'button','score':.9,'box':dict(x=0,y=0,width=10,height=10),**change}
    with pytest.raises(ValueError):validate_regions([r],100,100)

DRAFT={'title':'fixture','steps':[{'action':'click','selector':'#go','value':''},{'action':'assert_visible','selector':'#done','value':''}]}
def test_draft_compiles_no_execution():
    text=compile_draft(DRAFT,{'#go','#done'},'http://sut:8080/')
    assert text.startswith('# UNREVIEWED') and 'ASSERT_VISIBLE "#done"' in text and text.endswith('GUI_STOP\n')

@pytest.mark.parametrize('step',[{'action':'shell','selector':'#go','value':'id'},{'action':'assert_text','selector':'#go','value':'x\nSHELL id'},{'action':'assert_text','selector':'#go','value':'$TOKEN'},{'action':'assert_visible','selector':'#invented','value':''}])
def test_draft_refuses_expansion(step):
    with pytest.raises(ValueError):compile_draft({'title':'x','steps':[step]},{'#go'},'http://sut:8080')

def test_draft_needs_assertion():
    with pytest.raises(ValueError):compile_draft({'title':'x','steps':[DRAFT['steps'][0]]},{'#go'},'http://sut:8080')

def test_terminal_real_pty(tmp_path):
    pytest.importorskip('pexpect')
    from testwins.integrations.terminal import execute
    task={'command':sys.executable,'args':['-c','name=input("Name: "); print("Hello",name)'],
          'steps':[{'action':'expect','value':'Name: '},{'action':'send','value':'Testwins'},{'action':'expect','value':'Hello Testwins'},{'action':'eof'}]}
    r=execute(task,tmp_path,tmp_path)
    assert r['status']=='passed' and r['executed']==4 and r['exit_code_matched']

def test_terminal_nonzero_exit_fails(tmp_path):
    pytest.importorskip('pexpect')
    from testwins.integrations.terminal import execute
    r=execute({'command':sys.executable,'args':['-c','raise SystemExit(7)'],'steps':[{'action':'eof'}]},tmp_path,tmp_path)
    assert r['status']=='failed' and r['exit_status']==7

def test_terminal_output_budget_even_no_match(tmp_path):
    pytest.importorskip('pexpect')
    from testwins.integrations.terminal import execute
    with pytest.raises(ValueError,match='budget'):
        execute({'command':sys.executable,'args':['-c','print("a"*10000)'],'max_output_bytes':1024,'steps':[{'action':'expect','value':'notfound'}]},tmp_path,tmp_path)

def test_landing_local_assets_and_no_fictional_install():
    root=Path(__file__).resolve().parents[1]/'landing/static'
    text=(root/'index.html').read_text()
    assert 'make landing-check' in text and 'pip install testwins' not in text
    assert 'https://fonts.' not in text and '<script src="/app.js"' in text

def test_sdk_bridge_uses_public_contract_with_explicit_fake(tmp_path,monkeypatch):
    """Dependency injection tests transport, not a claim of an installed TestQL run."""
    import types
    from testwins.integrations.testql import execute
    calls=[]
    class Request:
        def __init__(self,**kwargs):self.kwargs=kwargs;self.dry_run=kwargs['dry_run'];self.request_hash='a'*64;calls.append(kwargs)
        def to_dict(self):return {'schema':'testql.verification-request.v1','request_hash':self.request_hash}
    mod=types.ModuleType('testql.verification');mod.VerificationRequest=Request
    mod.run_verification=lambda req:SimpleNamespace(to_dict=lambda:payload())
    mod.verification_contract_schema=lambda name:{'type':'object','required':['schema','result_hash','runs']}
    pkg=types.ModuleType('testql');pkg.__path__=[]
    monkeypatch.setitem(sys.modules,'testql',pkg);monkeypatch.setitem(sys.modules,'testql.verification',mod)
    monkeypatch.setattr('importlib.metadata.version',lambda name:'fixture-not-real-sdk')
    result=execute(TASK,tmp_path,tmp_path/'out')
    assert result['status']=='passed' and result['engine_version']=='fixture-not-real-sdk'
    assert calls[0]['allow_semantic_events'] is False and calls[0]['quiet'] is True
    assert (tmp_path/'out/testql-result.json').exists()
