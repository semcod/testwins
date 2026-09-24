"""Rendered opaque coverage must not hide actual heading, target or control defects."""
import asyncio
import html
import json
import os
from unittest.mock import patch

import pytest
from playwright.async_api import Page, async_playwright

from testwins.config import load, validate
from testwins.detectors import detect
from testwins.frames import resolve
from testwins.runner import collect, run
from testwins.verification import verify_run

pytestmark = pytest.mark.browser
CONTRACT = {'id': 'toolbar', 'selector': '#toolbar', 'content': '#content'}


def document(old='<p id="old">Previous section text</p>', style=''):
    return f'''<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1">
    <style>body{{margin:0;font:20px/24px sans-serif}}#content{{min-height:2000px}}
    #toolbar{{position:sticky;top:0;height:60px;background:white;display:flex;align-items:center}}
    #old{{display:block;margin:0;height:40px;font:20px/24px sans-serif;padding:0;border:0}}
    h2{{margin:0;font:24px/32px sans-serif}}{style}</style>
    <main id="content"><div id="toolbar"><span id="title">Toolbar Print</span></div>
    {old}<div style="height:28px"></div><h2 id="target">Target heading</h2></main>'''


def parent(child):
    return '<!doctype html><style>body{margin:0;min-height:600px}iframe{position:absolute;left:20px;top:20px;width:500px;height:450px;border:0}</style><iframe id="guide" srcdoc="'+html.escape(child, quote=True)+'"></iframe>'


def config(frame=False):
    cfg = load(); cfg.update(headless=True, matrix='chromium')
    cfg['devices'] = {'desktop': {'width': 600, 'height': 600, 'dpr': 1, 'touch': False, 'mobile': False}}
    cfg['capture'].update(repeats=1, scroll_tiles=1, settle_ms=0, ready_selector='body')
    cfg['axe']['enabled'] = False
    cfg['sticky_regions'] = [dict(CONTRACT, **({'frame': 'guide'} if frame else {}))]
    if frame:
        cfg['frames'] = [{'id': 'guide', 'selector': '#guide'}]
        cfg['routes'][0]['frames'] = ['guide']
    if os.environ.get('CHROMIUM_EXECUTABLE'): cfg['executables']['chromium'] = os.environ['CHROMIUM_EXECUTABLE']
    return validate(cfg)


def overlap(findings, selector='#old'):
    return any(f['rule'] == 'TW-TEXT-OVERLAP' and selector in f['selectors'] for f in findings)


async def observe(page, cfg):
    snap = await collect(page, None, cfg)
    return snap, detect(snap, cfg, cfg['devices']['desktop'])


async def browser_check(callback):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_EXECUTABLE'), headless=True, args=['--no-sandbox'])
        page = await browser.new_page(viewport={'width': 600, 'height': 600})
        try: await callback(page)
        finally: await browser.close()


@pytest.mark.parametrize('frame', [False, True])
def test_explicit_opaque_coverage_is_scoped_and_keeps_raw_ranges(frame):
    async def check(page):
        cfg = config(frame); await page.set_content(parent(document()) if frame else document())
        surface = await resolve(page, cfg, 'guide') if frame else page
        snap, _ = await observe(surface, cfg)
        assert snap['sticky_regions'][0]['state'] == 'inactive'
        await surface.evaluate('() => scrollTo(0,55)')
        snap, findings = await observe(surface, cfg)
        evidence = snap['sticky_regions'][0]
        assert evidence['state'] == 'active' and evidence['coverage']
        assert all(c['selector'] == '#old' for c in evidence['coverage'])
        assert any(t['selector'] == '#old' and t['text'] for t in snap['texts'])
        assert not overlap(findings)
        cfg['sticky_regions'] = []
        assert overlap(detect(snap, cfg, cfg['devices']['desktop']))
        if frame:
            root, _ = await observe(page, config(frame))
            assert root['sticky_regions'] == []
    asyncio.run(browser_check(check))


@pytest.mark.parametrize('old', [
    '<h2 id="old">Previous heading</h2>', '<p id="old" role="heading">Heading</p>',
    '<button id="old">Background control</button>', '<a id="old" href="#target">Background link</a>',
    '<p id="old" tabindex="0">Focusable text</p>',
])
def test_headings_and_controls_are_never_removed_from_overlap_checks(old):
    async def check(page):
        cfg = config(); await page.set_content(document(old)); await page.evaluate('scrollTo(0,55)')
        snap, findings = await observe(page, cfg)
        assert snap['sticky_regions'][0]['coverage'] == []
        assert overlap(findings)
        if '<button' in old or '<a' in old:
            assert any(f['rule'] == 'TW-CONTROL-OCCLUDED' and '#old' in f['selectors'] for f in findings)
    asyncio.run(browser_check(check))


def test_current_fragment_and_visible_collision_remain_reported():
    async def check(page):
        cfg = config(); await page.set_content(document())
        await page.evaluate("history.replaceState({}, '', '#old'); scrollTo(0,55)")
        snap, findings = await observe(page, cfg)
        assert snap['sticky_regions'][0]['coverage'] == [] and overlap(findings)
        await page.evaluate("history.replaceState({}, '', '#target'); document.querySelector('#content').insertAdjacentHTML('beforeend', '<p id=a style=\"position:absolute;top:300px\">Visible first</p><p id=b style=\"position:absolute;top:300px\">Visible second</p>')")
        _, findings = await observe(page, cfg)
        assert not overlap(findings) and overlap(findings, '#a')
    asyncio.run(browser_check(check))


@pytest.mark.parametrize('style', [
    '#toolbar{background:transparent}', '#toolbar{background:rgba(255,255,255,.5)}',
    '#content{opacity:.5}', '#toolbar{border-radius:30px}', '#toolbar{clip-path:inset(0 50% 0 0)}',
    '#toolbar{position:fixed;width:100%}', '#toolbar{transform:translateX(1px)}',
])
def test_unproven_paint_never_authorizes_exclusion(style):
    async def check(page):
        cfg = config(); await page.set_content(document(style=style)); await page.evaluate('scrollTo(0,55)')
        snap, findings = await observe(page, cfg)
        assert snap['sticky_regions'][0]['state'] == 'invalid'
        assert not snap['sticky_regions'][0]['coverage']
        assert any(f['rule'] == 'TW-STICKY-CONTRACT' for f in findings)
        raw = config(); raw['sticky_regions'] = []
        assert overlap(findings) == overlap(detect(snap, raw, raw['devices']['desktop']))
        assert any(g['kind'] == 'sticky_contract' for g in snap['gaps'])
    asyncio.run(browser_check(check))


def test_partial_range_and_header_pointer_holes_keep_overlap():
    async def check(page):
        cfg = config(); await page.set_content(document(style='#old{font-size:80px;line-height:80px}'))
        await page.evaluate('scrollTo(0,55)')
        snap, findings = await observe(page, cfg)
        assert snap['sticky_regions'][0]['coverage'] == [] and overlap(findings)
        await page.set_content(document(style='#toolbar{pointer-events:none}'))
        await page.evaluate('scrollTo(0,55)')
        snap, findings = await observe(page, cfg)
        assert snap['sticky_regions'][0]['coverage'] == [] and overlap(findings)
    asyncio.run(browser_check(check))


@pytest.mark.parametrize('style', [
    '#old{position:relative;z-index:10;pointer-events:none}',
    '#old{position:absolute;top:60px}',
])
def test_floating_or_pointer_transparent_text_is_not_assumed_hidden(style):
    async def check(page):
        cfg = config(); await page.set_content(document(style=style)); await page.evaluate('scrollTo(0,55)')
        snap, findings = await observe(page, cfg)
        assert snap['sticky_regions'][0]['coverage'] == [] and overlap(findings)
    asyncio.run(browser_check(check))


@pytest.mark.parametrize('invalid', [False, True])
def test_frame_report_retains_evidence_and_invalid_contract_blocks_gate(tmp_path, invalid):
    async def fixture(page, url, **kwargs):
        await page.set_content(parent(document(style='#toolbar{background:transparent}' if invalid else '')))
        await page.frames[1].evaluate('scrollTo(0,55)')
    with patch.object(Page, 'goto', fixture): root = asyncio.run(run(config(True), tmp_path))
    verify_run(root); report = json.loads((root / 'report.json').read_text())
    observations = report['sticky_observations']
    assert observations and all(o['scope']['kind'] == 'frame' for o in observations)
    assert all(o['state'] == ('invalid' if invalid else 'active') for o in observations)
    assert report['gate']['exit_code'] == (2 if invalid else 0)
    if not invalid: assert all(o['coverage'] for o in observations)
    assert 'Sticky regions:' in (root / 'REPORT.md').read_text()
    assert 'Sticky regions:' in (root / 'index.html').read_text()
