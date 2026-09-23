"""Real Chromium probes and runner reports against owned UI fixtures."""
import asyncio
import json
import os
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest
from playwright.sync_api import sync_playwright

from testwins.ux import PROBE, assess

pytestmark = pytest.mark.browser
HTML = '''<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<style>button {padding:16px} .selected {background:rgb(0,120,60);color:white} #result {margin-top:20px}</style></head>
<body><button id="choose">Choose filter</button><p id="status" role="status" data-private></p><div id="result" tabindex="-1"></div>
<script>document.querySelector('#choose').onclick=()=>{
 document.querySelector('#choose').className='selected';
 document.querySelector('#status').textContent='Ready';
 document.querySelector('#result').textContent='Filtered';
 document.querySelector('#result').focus();
};</script></body></html>'''


@pytest.fixture
def page():
    executable = os.environ.get('CHROMIUM_EXECUTABLE') or shutil.which('chromium')
    if not executable: pytest.skip('Chromium not installed')
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=executable,headless=True,args=['--no-sandbox'])
        try:
            page = browser.new_page(); page.set_content(HTML)
            yield page
        finally: browser.close()


def spec(**extra):
    return {'strategy':'dashboard','habit':'standard','response_ms':3000,'feedback_ms':150,'motion_ms':200,
            'feedback':{'kind':'text','selector':'#status','value':'Ready'},'announce':True,
            'focus':'#result','visual_change':'#choose', **extra}


def probe(page, contract, action='click'):
    page.evaluate(PROBE,{'action':action,'selector':'#choose','contract':contract})


def finish(page, contract):
    return assess(contract, page.evaluate('() => window.__testwinsUX.complete()'), True)


def test_click_tracks_feedback_visual_change_and_focus(page):
    contract = spec(); probe(page,contract); page.locator('#choose').click()
    result = finish(page,contract)
    assert result['status'] == 'passed', result
    assert result['observations']['feedback_ms'] is not None
    assert 'Ready' not in json.dumps(result['observations'])


def test_keyboard_journey_observes_keydown(page):
    contract = spec(habit='keyboard');probe(page,contract,'press')
    page.locator('#choose').press('Enter')
    assert finish(page,contract)['status'] == 'passed'


def test_preexisting_feedback_and_unrelated_mutation_are_not_new_acknowledgement(page):
    page.locator('#status').evaluate("e => e.textContent='Ready'")
    page.locator('#choose').evaluate("e => e.onclick=()=>document.querySelector('#result').textContent='Other change'")
    contract=spec(); probe(page,contract);page.locator('#choose').click()
    result=finish(page,contract)
    assert result['status']=='failed'
    assert 'TW-UX-FEEDBACK-MISSING' in {v['rule'] for v in result['violations']}


def test_feedback_must_be_visible_and_announced(page):
    page.locator('#status').evaluate("e=>e.setAttribute('aria-live','off')")
    contract=spec();probe(page,contract);page.locator('#choose').click()
    assert 'TW-UX-STATUS-SEMANTICS' in {v['rule'] for v in finish(page,contract)['violations']}
    page.set_content(HTML.replace('role="status"', 'role="status" style="display:none"'))
    probe(page,contract);page.locator('#choose').click()
    assert 'TW-UX-FEEDBACK-MISSING' in {v['rule'] for v in finish(page,contract)['violations']}


def test_response_budget_is_independent_of_eventual_success(page):
    page.locator('#choose').evaluate("e=>e.onclick=()=>setTimeout(()=>document.querySelector('#result').textContent='Done',200)")
    contract=spec(response_ms=70);probe(page,contract);page.locator('#choose').click()
    page.wait_for_function("document.querySelector('#result').textContent==='Done'")
    assert 'TW-UX-RESPONSE-LATE' in {v['rule'] for v in finish(page,contract)['violations']}


def test_reduced_motion_detects_infinite_animation(page):
    page.emulate_media(reduced_motion='reduce')
    page.add_style_tag(content='@keyframes spin {to {transform:rotate(360deg)}} .selected {animation:spin 1s linear infinite}')
    contract=spec(habit='reduced-motion',motion='#choose',motion_ms=0)
    probe(page,contract);page.locator('#choose').click()
    assert 'TW-UX-MOTION-BUDGET' in {v['rule'] for v in finish(page,contract)['violations']}


def test_absent_motion_target_and_missing_input_are_incomplete(page):
    contract=spec(motion='#absent');probe(page,contract);page.locator('#choose').click()
    assert finish(page,contract)['reason']=='motion_target_not_observed'
    probe(page,spec())
    assert finish(page,spec())['reason']=='input_event_not_observed'


def test_ambiguous_feedback_selector_is_not_silently_first_match(page):
    page.locator('body').evaluate("e=>e.insertAdjacentHTML('beforeend','<p id=status>duplicate</p>')")
    with pytest.raises(Exception,match='ambiguous'):probe(page,spec())


@pytest.fixture
def server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            text = HTML if self.path == '/good' else HTML.replace('role="status"','')
            body = text.encode();self.send_response(200);self.send_header('Content-Type','text/html')
            self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def log_message(self,*args): pass
    server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread = threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield 'http://127.0.0.1:'+str(server.server_port)
    finally:server.shutdown();server.server_close();thread.join()


@pytest.mark.parametrize('mode,expected', [('good','passed'),('bad','failed')])
def test_full_runner_gate_integrity_reports_and_repair_export(tmp_path,server,mode,expected):
    from testwins.config import load,validate
    from testwins.runner import run
    from testwins.verification import verify_run
    from testwins.ux_review import review
    from testwins.proposals import validate_producer
    cfg=load(matrix='chromium',headless=True,base_url=server)
    cfg['devices']={'desktop':cfg['devices']['desktop']};cfg['routes']=[];cfg['axe']['enabled']=False
    cfg['capture'].update(repeats=1,scroll_tiles=1,settle_ms=20,freeze_animations=False)
    cfg['rules']['heuristic_alignment']=False
    cfg['ux']['strategy']='dashboard'
    cfg['journeys']=[{'id':'filter','path':'/'+mode,'steps':[{'id':'choose','action':'click','selector':'#choose','allow_mutation':True,
        'expect':{'kind':'text','selector':'#result','value':'Filtered'},
        'ux':{'feedback':{'kind':'text','selector':'#status','value':'Ready'},'announce':True,'focus':'#result','visual_change':'#choose','feedback_ms':150}}]}]
    validate(cfg)
    root=asyncio.run(run(cfg,tmp_path/'runs'));report=json.loads((root/'report.json').read_text())
    assert report['gate']['status']==expected, report['gate']
    assert report['checks'][0]['ux']['status']==expected
    assert verify_run(root)['manifest']=='verified'
    redacted=json.loads((root/'config.redacted.json').read_text())
    assert redacted['journeys'][0]['steps'][0]['ux']['feedback']['value']=='[OPERATOR EXPECTATION]'
    assert 'ux.json' in json.dumps(json.loads((root/'manifest.json').read_text())['evidence'])
    if mode=='bad':
        class Client:
            def call(self,messages):
                evidence=json.loads(messages[1]['content'])['evidence']
                return {'repairs':[{'evidence_id':e['evidence_id'],'diagnosis':'Status semantics absent','change':'Add role=status','verification':'Repeat choose; require announced feedback'} for e in evidence]}, {'backend':'test-double'}
        output=tmp_path/'review';result=review(root,output,{},client=Client())
        assert result['repairs'] and result['executed'] is False
        proposals=json.loads((output/'proposals.json').read_text())
        for proposal in proposals:validate_producer(proposal)
        assert all('needs-human' in p['labels'] and p['files']==[] for p in proposals)
        assert verify_run(root)['manifest']=='verified'


def test_unchanged_outcome_is_not_evidence_of_working_action(page):
    page.locator('#result').evaluate("e=>e.textContent='Already ready'")
    contract = spec()
    page.evaluate(PROBE, {'action':'click','selector':'#choose','contract':contract,
                          'outcome':{'kind':'text','selector':'#result','value':'Already ready'}})
    page.locator('#choose').evaluate("e=>e.onclick=()=>{}")
    page.locator('#choose').click()
    assert 'TW-UX-OUTCOME-UNCHANGED' in {v['rule'] for v in finish(page,contract)['violations']}
