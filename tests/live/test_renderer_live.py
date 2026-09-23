"""True Chromium/CDP measurements using only an explicitly loaded owned fixture.
No HTTP navigation is claimed: this runtime's URLBlocklist is left unchanged.
"""
import asyncio
import json
import shutil
import os
from pathlib import Path
import pytest
from testwins.live.config import WatchConfig,Target
from testwins.config import load
from testwins.live.scanner import BrowserScanner,OBSERVER
from testwins.live.store import Store

DIRTY='''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>
body{margin:0;font:16px/24px sans-serif;background:white;color:black}#wide{display:flex;width:100%}#long{white-space:nowrap}
#a,#b{position:absolute;left:20px;top:100px;margin:0}#clip{position:absolute;top:180px;height:12px;width:90px;overflow:hidden;white-space:nowrap}
button{margin-top:250px}#cover{position:absolute;left:0;top:250px;width:150px;height:60px;background:#ddd}
</style></head><body><div id="wide"><span id="long">LONG LONG LONG LONG LONG LONG LONG LONG LONG LONG LONG LONG LONG LONG LONG LONG LONG LONG LONG</span></div>
<p id="a">Text overlap one</p><p id="b">Text overlap two</p><p id="clip">Text clipped intentionally for test fixture</p><button id="action">Test action</button><div id="cover"></div></body></html>'''
CLEAN='''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><h1 id="ok">Ready</h1><p>No overlap in this controlled state.</p></body></html>'''

@pytest.mark.browser
def test_real_cdp_find_confirm_recover_and_css_provenance(tmp_path):
    exe=os.environ.get('CHROMIUM_EXECUTABLE')
    if not exe:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                if Path(p.chromium.executable_path).exists():exe=p.chromium.executable_path
        except Exception:pass
    if not exe:
        for name in ('google-chrome','google-chrome-stable','chromium','chromium-browser'):
            p=shutil.which(name)
            if p and not p.startswith('/snap/'):exe=p;break
    exe=exe or shutil.which('chromium')
    if not exe:pytest.skip('Chromium unavailable')
    audit=load();audit['executables']={'chromium':exe};audit['headless']=True;audit['axe']['enabled']=False;audit['rules']['heuristic_alignment']=False
    audit['capture']['settle_ms']=30;audit['capture']['timeout_ms']=1000
    t=Target('fixture:home:chromium:mobile','fixture','http://unused.invalid/','home',device='mobile',hot=True,audit=audit,
             expect=({'kind':'visible','selector':'#ok'},))
    cfg=WatchConfig('fixture',[t],tmp_path,tmp_path,max_hot_pages=1,repeat_gap_s=.05,css_provenance=True)
    store=Store(tmp_path/'live.sqlite');scanner=BrowserScanner(cfg)
    async def test():
        await scanner.start()
        try:
            ctx,page,cdp,transport,new=await scanner._page(t)
            await page.set_content(DIRTY);await page.evaluate(OBSERVER)
            first=await scanner.scan(t,2,'dom');second=await scanner.scan(t,2,'dom')
            assert first['transport']=='cdp';rules={f['rule'] for f in first['findings']}
            assert {'TW-TEXT-OVERLAP','TW-TEXT-CLIPPED','TW-VIEWPORT-OVERFLOW','TW-EXPECTATION'}<=rules
            assert first['status']=='complete',first['gaps']
            for r in (first,second):store.record(t.id,t.scope,r)
            assert store.status()['totals']['confirmed']>=4
            overlap=next(f for f in first['findings'] if f['rule']=='TW-TEXT-OVERLAP')
            assert overlap['diagnosis']['hypotheses'][0]['id']=='position-layer'
            assert (tmp_path/first['evidence']/'rendered-css.json').exists()
            await page.set_content(CLEAN)
            for _ in range(3):store.record(t.id,t.scope,await scanner.scan(t,2,'dom'))
            assert not [i for i in store.status()['incidents'] if i['state']=='confirmed']
        finally:await scanner.close()
    try:asyncio.run(test())
    finally:store.close()
