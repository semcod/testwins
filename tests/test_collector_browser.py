"""Opt-in real renderer tests; only our inline fixture is loaded (no HTTP)."""
from pathlib import Path
import os,shutil
import pytest

@pytest.mark.browser
def test_closed_details_are_not_rendered_text():
    from playwright.sync_api import sync_playwright
    from testwins.browser import find_chromium
    executable=find_chromium()
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
            page.set_content('''
              <header><a id="nav-dup">15 zł/h pracy agenta/humanoida</a></header>
              <main>
                <p id="b1">15 zł/h pracy agenta/humanoida w ekosystemie z nadzorem człowieka.</p>
                <div style="height:1600px"></div>
                <p id="b2">15 zł/h pracy agenta/humanoida w ekosystemie z nadzorem człowieka.</p>
                <svg id="g1" width="120" height="80" viewBox="0 0 120 80"><title id="svg-title-1">Powtarzalny tytuł SVG powyżej 18 znaków</title><path id="path-1" d="M10 10H110"/></svg>
                <svg id="g2" width="120" height="80" viewBox="0 0 120 80"><title id="svg-title-2">Powtarzalny tytuł SVG powyżej 18 znaków</title><path id="path-2" d="M10 10H110"/></svg>
                <svg id="icon-small" width="24" height="24" viewBox="0 0 24 24"><path d="M2 12h20"/></svg>
              </main>
              <footer><span id="foot-dup">15 zł/h pracy agenta/humanoida</span></footer>
            ''')
            offer_snap=page.evaluate(script,options)
            block_sels={b['selector'] for b in offer_snap['content_blocks']}
            assert {'#b1','#b2'}<=block_sels
            assert '#nav-dup' not in block_sels and '#foot-dup' not in block_sels
            assert '#svg-title-1' not in block_sels and '#svg-title-2' not in block_sels
            node_sels={n['selector'] for n in offer_snap['nodes']}
            assert '#path-1' not in node_sels and '#path-2' not in node_sels
            graphic_sels={g['selector'] for g in offer_snap['graphics']}
            assert {'#g1','#g2'}<=graphic_sels
            assert '#icon-small' not in graphic_sels
        finally:browser.close()
