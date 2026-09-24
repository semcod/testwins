"""Rendered evidence for empty CSS clip paths, including accessibility controls."""
from pathlib import Path
import os
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
        yield browser
        browser.close()

@pytest.fixture
def page(browser):
    page = browser.new_page()
    page.set_content('''<style>
      .sr-only {position:absolute;width:1px;height:1px;overflow:hidden;white-space:nowrap}
    </style><span id="status" class="sr-only" role="status" aria-live="polite">Runtime online</span>
    <p id="visible">Visible content</p>''')
    yield page
    page.close()

def findings(snapshot):
    cfg = load()
    return detect(snapshot, cfg, cfg['devices']['desktop'])

@pytest.mark.parametrize('clip', [
    'inset(50%)', 'inset(0% 50%)', 'inset(100% 0% 0%)',
    'inset(0 75% 0 25%)', 'inset(60%)', 'inset(50% round 4px)',
    'inset(50%) content-box',
])
def test_empty_inset_does_not_turn_live_region_into_visual_defect(page, clip):
    page.locator('#status').evaluate('(el, clip) => el.style.clipPath = clip', clip)
    snapshot = page.evaluate(COLLECTOR, OPTIONS)
    assert '#status' not in {text['selector'] for text in snapshot['texts']}
    status = next(n for n in snapshot['nodes'] if n['selector'] == '#status')
    assert status['fullyClipped'] is True
    assert status['css']['clipPath'].startswith('inset(')
    assert not [f for f in findings(snapshot) if '#status' in f['selectors']]
    assert '#visible' in {text['selector'] for text in snapshot['texts']}
    assert page.get_by_role('status').get_attribute('aria-live') == 'polite'

@pytest.mark.parametrize('clip', ['none', 'inset(0%)', 'inset(49.999%)',
    'inset(calc(50% - 1px))', 'circle(50%)', 'polygon(0 0,100% 0,100% 100%,0 100%)'])
def test_role_class_and_partial_or_unknown_clip_do_not_suppress_overflow(page, clip):
    page.locator('#status').evaluate('(el, clip) => el.style.clipPath = clip', clip)
    snapshot = page.evaluate(COLLECTOR, OPTIONS)
    assert any(f['rule'] == 'TW-TEXT-CLIPPED' and '#status' in f['selectors'] for f in findings(snapshot))

@pytest.mark.parametrize('shadow', [False, True])
def test_empty_ancestor_clip_applies_to_descendants_across_shadow_root(page, shadow):
    page.locator('#status').evaluate('''(el, shadow) => {
      const root = shadow ? el.attachShadow({mode:'open'}) : el;
      root.innerHTML = '<span id="descendant">Still accessible text</span>';
      el.style.clipPath = 'inset(50%)';
    }''', shadow)
    snapshot = page.evaluate(COLLECTOR, OPTIONS)
    assert not [t for t in snapshot['texts'] if 'descendant' in t['selector']]
    assert any(n['fullyClipped'] for n in snapshot['nodes'] if 'descendant' in n['selector'])


def test_focused_clipped_control_remains_evidence_and_blocks_complete_observation(page):
    page.set_content('''<button id="control" style="clip-path:inset(50%)">Hidden action</button>''')
    page.locator('#control').focus()
    snapshot = page.evaluate(COLLECTOR, OPTIONS)
    control = next(n for n in snapshot['nodes'] if n['selector'] == '#control')
    assert control['interactive'] and control['focused'] and control['fullyClipped']
    assert any(g['kind'] == 'focused_clipped_control' and g['selector'] == '#control' for g in snapshot['gaps'])
    page.add_style_tag(content='#control:focus {clip-path:none !important}')
    visible = page.evaluate(COLLECTOR, OPTIONS)
    assert not next(n for n in visible['nodes'] if n['selector'] == '#control')['fullyClipped']
    assert '#control' in {t['selector'] for t in visible['texts']}
    assert not visible['gaps']
