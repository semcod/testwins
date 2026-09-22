"""Opt-in real renderer tests; only our inline fixture is loaded (no HTTP)."""
from pathlib import Path
import os,shutil
import pytest

@pytest.mark.browser
def test_closed_details_are_not_rendered_text():
    from playwright.sync_api import sync_playwright
    executable=os.environ.get('CHROMIUM_EXECUTABLE') or shutil.which('chromium')
    if not executable:pytest.skip('No system Chromium for this explicit renderer fixture')
    script=(Path(__file__).resolve().parents[1]/'testwins/collector.js').read_text()
    options=dict(mask_selectors=[],max_elements=500,max_text_rects=1000,max_html_bytes=100000,alignment=[])
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=executable,headless=True,args=['--no-sandbox'])
        try:
            page=browser.new_page();page.set_content('''<details id="closed"><summary id="summary">Summary</summary><p id="answer">Hidden answer</p></details><p id="visible">Painted text</p>''')
            before=page.evaluate(script,options)
            assert '#answer' not in {t['selector'] for t in before['texts']}
            assert {'#summary','#visible'}<={t['selector'] for t in before['texts']}
            page.locator('#summary').click()
            after=page.evaluate(script,options)
            assert '#answer' in {t['selector'] for t in after['texts']}
        finally:browser.close()
