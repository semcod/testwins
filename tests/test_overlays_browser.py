"""Actual hit tests retain unexpected blockers, including during menu recovery."""
import os
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from testwins.config import load
from testwins.detectors import detect

pytestmark=pytest.mark.browser
COLLECTOR=(Path(__file__).resolve().parents[1]/'testwins/collector.js').read_text()
CONTRACT={'id':'language','trigger':'#trigger','overlay':'#menu','background':['#background']}
MARKUP='''<!doctype html><style>
body{margin:0}button{width:100px;height:40px}
#background{position:absolute;left:120px;top:60px}
#menu{position:absolute;left:110px;top:50px;width:140px;height:80px;background:white;z-index:2}
#option{margin:10px}#unexpected{position:absolute;left:120px;top:60px;width:100px;height:40px;z-index:3}
[hidden]{display:none!important}</style>
<button id="trigger" aria-controls="menu" aria-expanded="true">Language</button>
<button id="background">Background</button>
<div id="menu"><button id="option">English</button></div>'''


@pytest.fixture(scope='module')
def browser():
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_EXECUTABLE'),headless=True,args=['--no-sandbox'])
        try: yield browser
        finally: browser.close()


@pytest.fixture
def page(browser):
    page=browser.new_page(viewport={'width':400,'height':300})
    page.set_content(MARKUP)
    try: yield page
    finally: page.close()


def observe(page,contract=CONTRACT):
    cfg=load();cfg['overlays']=[contract]
    opts=dict(cfg['capture'],alignment=[],overlays=cfg['overlays'])
    snapshot=page.evaluate(COLLECTOR,opts)
    return snapshot,detect(snapshot,cfg,cfg['devices']['desktop'])


def occluded(findings,selector):
    return any(f['rule']=='TW-CONTROL-OCCLUDED' and selector in f['selectors'] for f in findings)


def test_intended_background_coverage_has_hit_evidence(page):
    snapshot,findings=observe(page)
    evidence=snapshot['overlays'][0]
    assert evidence['state']=='active' and not evidence['errors']
    assert evidence['coverage']==[{'selector':'#background','covering':['#option'], 'occluded':5,'hitSamples':5}]
    assert not occluded(findings,'#background')
    cfg=load()
    assert occluded(detect(snapshot,cfg,cfg['devices']['desktop']),'#background')


@pytest.mark.parametrize('mutation',[
    "document.querySelector('#trigger').setAttribute('aria-expanded','false')",
    "document.querySelector('#trigger').removeAttribute('aria-controls')",
    "document.querySelector('#menu').hidden=true",
    "document.querySelector('#trigger').disabled=true",
    "document.querySelector('#menu').setAttribute('aria-hidden','true')",
    "document.querySelector('#menu').inert=true",
    "document.body.append(document.querySelector('#menu').cloneNode(true))",
])
def test_invalid_relationship_never_authorizes_coverage(page,mutation):
    page.evaluate(mutation)
    snapshot,findings=observe(page)
    assert snapshot['overlays'][0]['state']=='invalid'
    assert not snapshot['overlays'][0]['coverage']
    assert any(f['rule']=='TW-OVERLAY-CONTRACT' for f in findings)
    # Inert overlays do not intercept pointer input. Invalid contracts must
    # retain exactly the ordinary hit-test result, including that distinction.
    cfg=load()
    raw=detect(snapshot,cfg,cfg['devices']['desktop'])
    assert occluded(findings,'#background') == occluded(raw,'#background')


@pytest.mark.parametrize('background',[['body'],['#missing'],['#option'],['#trigger'],['[']])
def test_invalid_background_is_a_failure(page,background):
    snapshot,findings=observe(page,dict(CONTRACT,background=background))
    assert snapshot['overlays'][0]['state']=='invalid'
    assert occluded(findings,'#background')
    assert any(f['rule']=='TW-OVERLAY-CONTRACT' for f in findings)


def test_unexpected_cover_is_not_allowed_even_above_the_menu(page):
    page.evaluate("document.body.insertAdjacentHTML('beforeend','<div id=unexpected></div>')")
    snapshot,findings=observe(page)
    assert snapshot['overlays'][0]['coverage']==[]
    assert occluded(findings,'#background')
    assert occluded(findings,'#option')


def test_closed_menu_does_not_hide_a_stuck_cover_or_other_controls(page):
    page.evaluate("document.querySelector('#trigger').setAttribute('aria-expanded','false');document.querySelector('#menu').hidden=true;document.body.insertAdjacentHTML('beforeend','<div id=unexpected></div>')")
    snapshot,findings=observe(page)
    assert snapshot['overlays'][0]['state']=='inactive'
    assert occluded(findings,'#background')
    page.locator('#unexpected').evaluate('(e)=>e.remove()')
    assert not occluded(observe(page)[1],'#background')


def test_only_explicit_background_controls_are_authorized(page):
    page.evaluate("document.body.insertAdjacentHTML('beforeend','<button id=other style=\"position:absolute;left:120px;top:60px\">Other</button>')")
    snapshot,findings=observe(page)
    assert not occluded(findings,'#background')
    assert occluded(findings,'#other')
