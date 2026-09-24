"""Real Chromium evidence with controlled mutations at the screenshot boundary.

Owned inline fixtures: no HTTP/application coverage is claimed by these tests.
"""
import asyncio
import json
import os
from unittest.mock import patch

import pytest
from PIL import Image
from playwright.async_api import Page

from testwins.config import load
from testwins.live.config import Target, WatchConfig
from testwins.live.scanner import BrowserScanner
from testwins.runner import run
from testwins.verification import verify_run

pytestmark = pytest.mark.browser
MARKUP = '''<!doctype html><meta name="viewport" content="width=device-width">
<style>body{margin:0;font:16px/24px monospace}#clock{width:200px;height:24px}
#target{position:absolute;left:10px;top:60px;width:100px;height:40px}
#cover{position:absolute;left:10px;top:60px;width:100px;height:40px;z-index:-1}
#private{position:absolute;left:20px;top:150px;width:20px;height:20px;background:red}
</style><div id="clock">00:00:00</div><button id="target">OK</button>
<div id="cover"></div><div id="private" data-private>XX</div>'''


def config():
    cfg = load(matrix='chromium', headless=True)
    if os.environ.get('CHROMIUM_EXECUTABLE'):
        cfg['executables']['chromium'] = os.environ['CHROMIUM_EXECUTABLE']
    cfg['devices'] = {'desktop': cfg['devices']['desktop']}
    cfg['axe']['enabled'] = False
    cfg['rules']['heuristic_alignment'] = False
    cfg['capture'].update(repeats=1, scroll_tiles=1, settle_ms=0,
                          freeze_animations=False, timeout_ms=2000, max_cell_seconds=30)
    cfg['routes'] = [{'id': 'fixture', 'path': '/'}]
    return cfg


@pytest.mark.parametrize('change', ['clock', 'text-move', 'cover', 'private-move', 'settles'])
def test_batch_capture_keeps_geometry_state_content_and_final_retry_evidence(tmp_path, change):
    screenshots = []
    original = Page.screenshot

    async def fixture(page, url, **kwargs):
        await page.set_content(MARKUP)

    async def mutate_then_capture(page, **kwargs):
        attempt = len(screenshots) + 1
        if change == 'clock':
            await page.locator('#clock').evaluate('(e)=>e.textContent="00:00:01"')
        elif change == 'text-move':
            await page.locator('#clock').evaluate('(e,x)=>e.style.textIndent=x+"px"', attempt * 10)
        elif change == 'cover':
            await page.locator('#cover').evaluate('(e,x)=>e.style.zIndex=x', attempt)
        elif change == 'private-move' or (change == 'settles' and attempt == 1):
            await page.locator('#private').evaluate('(e,x)=>e.style.left=x+"px"', 20 + attempt * 40)
        screenshots.append(await original(page, **kwargs))
        return screenshots[-1]

    with patch.object(Page, 'goto', fixture), patch.object(Page, 'screenshot', mutate_then_capture):
        root = asyncio.run(run(config(), tmp_path))
    verify_run(root)
    report = json.loads((root / 'report.json').read_text())
    evidence = report['snapshots'][0]
    snapshot = json.loads((root / evidence['data']).read_text())
    stability = snapshot['stability']
    assert stability == evidence['stability']
    assert len(screenshots) == (1 if change == 'clock' else 2)
    assert stability['attempts'] == len(screenshots)
    if change == 'clock':
        assert snapshot['stable'] and not stability['content']
        assert report['gate']['status'] == 'passed'
        assert report['observation_stability'] == dict(measured=1,unmeasured=0,
            layout_changed=0,state_changed=0,content_changed=1)
        assert 'treści: 1' in (root / 'REPORT.md').read_text()
        assert 'treści: 1' in (root / 'index.html').read_text()
        assert next(t for t in snapshot['texts'] if t['selector']=='#clock')['text']=='00:00:01'
    elif change == 'settles':
        assert snapshot['stable'] and report['gate']['status'] == 'passed'
    else:
        assert not snapshot['stable'] and report['gate']['exit_code'] == 2
        assert any(g['kind']=='unstable_layout' for g in evidence['gaps'])
        if change == 'cover':
            assert stability['layout'] and not stability['state']
            assert any(f['rule']=='TW-CONTROL-OCCLUDED' for f in report['findings'])
        else:
            assert not stability['layout']
    if change == 'private-move':
        private = next(n for n in snapshot['nodes'] if n['selector']=='#private')
        assert private['rect']['x'] == 100  # final attempt, not the first retry's DOM
        assert 'XX' not in (root / evidence['html']).read_text()
        assert {60,100} <= {r['x'] for r in snapshot['masks']}
        image = Image.open(root / evidence['image']).convert('RGB')
        assert image.getpixel((65,155)) == image.getpixel((105,155)) == (35,35,35)


@pytest.mark.parametrize('moving', [False, True])
def test_live_scanner_uses_the_same_stability_assessment(tmp_path, moving):
    original = Page.screenshot

    async def mutate_then_capture(page, **kwargs):
        await page.locator('#clock').evaluate('(e)=>e.textContent="00:00:01"')
        if moving:
            await page.locator('#clock').evaluate('(e)=>e.style.textIndent="10px"')
        return await original(page, **kwargs)

    async def task():
        audit = config()
        target = Target('fixture', 'fixture', 'http://unused.invalid/', 'home',
                        device='desktop', hot=True, audit=audit)
        cfg = WatchConfig('fixture', [target], tmp_path, tmp_path, max_hot_pages=1, repeat_gap_s=0)
        scanner = BrowserScanner(cfg)
        await scanner.start()
        try:
            _,page,_,_,_ = await scanner._page(target)
            await page.set_content(MARKUP)
            with patch.object(Page, 'screenshot', mutate_then_capture):
                result = await scanner.scan(target, 1, 'dom')
            assert result['status'] == ('partial' if moving else 'complete'), result
            assert result['stability']['layout'] is not moving
            assert not result['stability']['content']
            assert any(g['kind']=='unstable_layout' for g in result['gaps']) is moving
        finally:
            await scanner.close()
    asyncio.run(task())
