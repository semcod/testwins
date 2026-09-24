"""Real rendered targets: distinguish scroll folds from permanently small areas."""
import os
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from testwins.config import load
from testwins.detectors import detect

pytestmark = pytest.mark.browser
COLLECTOR = (Path(__file__).resolve().parents[1] / 'testwins/collector.js').read_text()
OPTIONS = dict(mask_selectors=[], max_elements=500, max_text_rects=1000,
               max_html_bytes=100000, alignment=[])


@pytest.fixture(scope='module')
def browser():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_EXECUTABLE'),
                                     headless=True, args=['--no-sandbox'])
        try:
            yield browser
        finally:
            browser.close()


@pytest.mark.parametrize('markup,small', [
    ('<div class="port"><div class="spacer"></div><button id="target">OK</button></div>', False),
    ('<div class="port horizontal"><span class="spacer"></span><button id="target">OK</button></div>', False),
    ('<div class="port" style="overflow:hidden"><div class="spacer"></div><button id="target">OK</button></div>', True),
    ('<div class="port"><div class="spacer"></div><button id="target" style="height:16px">OK</button></div>', True),
    ('<div class="port" style="height:12px"><button id="target">OK</button></div>', True),
    ('<div style="height:100px;overflow:hidden"><div class="port"><div class="spacer"></div><button id="target">OK</button></div></div>', False),
    ('<div class="port"><div class="spacer"></div><div style="height:12px;overflow:hidden"><button id="target">OK</button></div></div>', True),
    ('<div style="height:288px"></div><button id="target">OK</button>', False),
    ('<div style="height:600px"></div><button id="target" style="position:fixed;bottom:-32px">OK</button>', True),
    ('<div class="port"><button id="target" style="position:relative;top:-32px">OK</button><div style="height:200px"></div></div>', True),
    ('<div style="height:12px;overflow:hidden"><div class="port"><button id="target">OK</button><div style="height:200px"></div></div></div>', True),
], ids=['vertical-scroll', 'horizontal-scroll', 'hard-clip', 'small-button',
        'small-scrollport', 'outer-hard-clip', 'inner-hard-clip', 'page-scroll',
        'fixed-target', 'unreachable-negative-overflow', 'outer-small-window'])
def test_visible_fragment_does_not_define_target_size(browser, markup, small):
    page = browser.new_page(viewport={'width':400, 'height':300})
    try:
        page.set_content('''<!doctype html><meta name="viewport" content="width=device-width">
        <style>body{margin:0}button{width:44px;height:44px;box-sizing:border-box;padding:0;border:0}
        .port{width:100px;height:100px;overflow:auto}.spacer{height:88px}
        .horizontal{white-space:nowrap}.horizontal .spacer{display:inline-block;width:88px;height:1px}
        </style>''' + markup)
        snapshot = page.evaluate(COLLECTOR, OPTIONS)
        target = next(n for n in snapshot['nodes'] if n['selector']=='#target')
        assert 0 < min(target['visibleRect']['width'], target['visibleRect']['height']) < 24
        cfg = load()
        findings = detect(snapshot, cfg, cfg['devices']['mobile'])
        actual = [f for f in findings if f['rule']=='TW-TARGET-SMALL' and '#target' in f['selectors']]
        assert bool(actual) is small, target
        assert page.evaluate('scrollY') == 0
        assert page.locator('.port').evaluate_all('(ports)=>ports.every(p=>p.scrollTop===0 && p.scrollLeft===0)')
    finally:
        page.close()


@pytest.mark.parametrize('axis,rtl', [('y',False),('x',False),('x',True)])
def test_already_scrolled_targets_keep_hit_testing_and_scroll_position(browser, axis, rtl):
    page = browser.new_page(viewport={'width':400,'height':300})
    try:
        page.set_content('''<!doctype html><style>body{margin:0}
            #port{width:100px;height:100px;overflow:auto}
            button{width:44px;height:44px;border:0;padding:0;box-sizing:border-box}
            .spacer{height:60px} .tail{height:200px}
            #port.horizontal{white-space:nowrap}
            .horizontal .spacer,.horizontal .tail{display:inline-block;height:1px}
            .horizontal .spacer{width:60px}.horizontal .tail{width:200px}
            </style><div id="port"><span class="spacer" style="display:block"></span><button id="target">OK</button><span class="tail" style="display:block"></span></div>''')
        if axis=='x':
            page.locator('#port').evaluate('(p)=>{p.className="horizontal";p.querySelectorAll("span").forEach(s=>s.style.display="inline-block")}')
        if rtl:
            page.locator('#port').evaluate('(p)=>p.style.direction="rtl"')
        page.locator('#port').evaluate('(p,v)=>p[v.axis==="x"?"scrollLeft":"scrollTop"]=v.offset',
                                       {'axis':axis,'offset':-88 if rtl else 88})
        before=page.locator('#port').evaluate('(p)=>[p.scrollLeft,p.scrollTop]')
        snapshot=page.evaluate(COLLECTOR,OPTIONS)
        target=next(n for n in snapshot['nodes'] if n['selector']=='#target')
        assert 0 < target['visibleRect']['width' if axis=='x' else 'height'] < 24
        assert target['targetSize']=={'width':44,'height':44}
        assert target['hitSamples']==5 and target['occluded']==0
        assert page.locator('#port').evaluate('(p)=>[p.scrollLeft,p.scrollTop]')==before
        vr=target['visibleRect']
        page.locator('body').evaluate('''(body,r)=>{const cover=document.createElement('div');
            cover.id='cover';cover.style.cssText=`position:fixed;z-index:10;left:${r.x}px;top:${r.y}px;width:${r.width}px;height:${r.height}px`;
            body.append(cover)}''',vr)
        cfg=load();covered=detect(page.evaluate(COLLECTOR,OPTIONS),cfg,cfg['devices']['mobile'])
        assert any(f['rule']=='TW-CONTROL-OCCLUDED' and '#target' in f['selectors'] for f in covered)
    finally:
        page.close()
