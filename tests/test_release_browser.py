"""Actual Chromium/CDP tests of 0.4 features. Inline owned fixtures, not HTTP portal validation."""
from __future__ import annotations
import asyncio
import copy
import json
import os
import shutil
from pathlib import Path
from unittest.mock import patch
import pytest
from testwins.config import load
from testwins.browser import launch,context_options
from testwins.sessions import save_private
from testwins.runner import run,assertion,act,guard
from testwins.downloads import inspect_download
from testwins.verification import verify_run
from playwright.async_api import async_playwright,Page,expect

pytestmark=pytest.mark.browser


def config():
    c=load(matrix='chromium',headless=True)
    c['devices']={'desktop':c['devices']['desktop']};c['axe']['enabled']=False
    c['capture'].update(repeats=1,scroll_tiles=1,settle_ms=30,timeout_ms=400,max_cell_seconds=30)
    c['rules']['heuristic_alignment']=False
    exe=os.environ.get('CHROMIUM_EXECUTABLE') or shutil.which('chromium')
    if not exe:pytest.skip('Set CHROMIUM_EXECUTABLE to an installed Chromium binary')
    c['executables']['chromium']=exe
    return c


def evidence(tmp_path,name):
    root=Path(os.environ.get('TW_RELEASE_EVIDENCE',str(tmp_path)))
    p=root/name;p.mkdir(parents=True,exist_ok=True);return p


@pytest.mark.integration
def test_real_download_event_and_content_validation(tmp_path):
    async def task():
        c=config();c['downloads']['enabled']=True
        async with async_playwright() as pw:
            async with launch(pw,'chromium',c) as (browser,transport):
                assert transport=='cdp'
                ctx=await browser.new_context(**context_options(c,c['devices']['desktop'],'chromium'))
                try:
                    await guard(ctx,c);page=await ctx.new_page();cdp=await ctx.new_cdp_session(page)
                    await page.set_content('''<button id="download" style="padding:20px" onclick="const a=document.createElement('a');a.href=URL.createObjectURL(new Blob(['Testwins controlled content'],{type:'text/plain'}));a.download='fixture.txt';a.click()">Download</button>''')
                    async with page.expect_download(timeout=5000) as pending:
                        await act(page,{'action':'download','selector':'#download'},cdp,c['devices']['desktop'],2000)
                    result=await inspect_download(await pending.value,{'filename_regex':r'fixture\.txt','starts_with_hex':'5465737477696e73'},c['downloads'],evidence(tmp_path,'download'))
                    assert result['status']=='passed' and not result['retained']
                finally:await ctx.close()
    asyncio.run(task())


@pytest.mark.integration
def test_real_storage_state_roundtrip_without_recording_tokens(tmp_path):
    async def task():
        c=config();path=tmp_path/'.auth/user.json'
        state={'cookies':[],'origins':[{'origin':'http://sut:8080','localStorage':[{'name':'token','value':'SYNTHETIC_AUTH_TOKEN'}]}]}
        save_private(path,state);c['sessions']={'user':{'storage_state':str(path)}};c['default_session']='user'
        async with async_playwright() as pw:
            async with launch(pw,'chromium',c) as (browser,_):
                ctx=await browser.new_context(**context_options(c,c['devices']['desktop'],'chromium'))
                try:
                    actual=await ctx.storage_state()
                    assert any(s.get('origin')=='http://sut:8080' for s in actual['origins'])
                finally:await ctx.close()
    asyncio.run(task())


def test_single_failure_one_repeat_blocks_gate_in_real_runner(tmp_path,monkeypatch):
    c=config();c['routes']=[]
    c['performance'].update(enabled=True,budgets={'JSHeapUsedSize':100_000_000})
    c['journeys']=[{'id':'flow','path':'/','steps':[{'id':'result','action':'assert','expect':{'kind':'text','selector':'#result','value':'EXPECTED'}}]}]
    async def own_fixture(page,url,**kw):
        assert url=='http://sut:8080/'
        await page.set_content('<meta name="viewport" content="width=device-width,initial-scale=1"><p id="result">ACTUAL</p>')
    monkeypatch.setenv('TW_VERIFICATION_FIXTURE','release-inline-fixture-no-http')
    with patch.object(Page,'goto',own_fixture):root=asyncio.run(run(c,evidence(tmp_path,'single-failure')))
    r=json.loads((root/'report.json').read_text())
    assert r['summary']['confirmed']==0 and r['summary']['candidate']>=1
    assert r['gate']['exit_code']==1 and r['checks'][0]['status']=='failed'
    assert r['checks'][0]['before'] and r['checks'][0]['after']
    assert all(s['performance']['status']=='passed' for s in r['snapshots'])
    verify_run(root)


def test_missing_browser_keeps_all_planned_steps(tmp_path):
    c=config();c['executables']['chromium']='/definitely-absent-testwins-browser'
    c['routes']=[];c['journeys']=[{'id':'flow','path':'/','steps':[{'id':'check','action':'assert','expect':{'kind':'visible','selector':'#x'}}]}]
    root=asyncio.run(run(c,evidence(tmp_path,'unavailable')))
    r=json.loads((root/'report.json').read_text())
    assert len(r['checks'])==1 and r['checks'][0]['status']=='not_run'
    assert r['gate']['exit_code']==2;verify_run(root)


def test_actual_extended_ui_expectations():
    async def task():
        c=config()
        async with async_playwright() as pw:
            async with launch(pw,'chromium',c) as (browser,_):
                page=await browser.new_page();page.set_default_timeout(700);expect.set_options(timeout=700)
                await page.set_content('<input id="field" value="hello"><input id="check" type="checkbox" checked><button id="disabled" disabled>Off</button><p id="text" data-state="ready">prefix expected suffix</p><ul><li>A</li><li>B</li></ul>')
                await page.locator('#field').focus()
                for spec in [{'kind':'focused','selector':'#field'},{'kind':'value','selector':'#field','value':'hello'},
                             {'kind':'checked','selector':'#check'},{'kind':'disabled','selector':'#disabled'},
                             {'kind':'contains_text','selector':'#text','value':'expected'},
                             {'kind':'attribute','selector':'#text','name':'data-state','value':'ready'},
                             {'kind':'count_min','selector':'li','value':2}]:
                    await assertion(page,spec,'',700)
                with pytest.raises(AssertionError):await assertion(page,{'kind':'count_min','selector':'li','value':3},'',100)
    asyncio.run(task())


def test_real_cookie_state_import():
    async def task():
        c=config()
        async with async_playwright() as pw:
            async with launch(pw,'chromium',c) as (browser,_):
                options=context_options(c,c['devices']['desktop'],'chromium')
                options['storage_state']={'cookies':[{'name':'fixture','value':'synthetic','domain':'sut','path':'/','expires':-1,'httpOnly':True,'secure':False,'sameSite':'Lax'}],'origins':[]}
                ctx=await browser.new_context(**options)
                try:assert any(x['name']=='fixture' for x in await ctx.cookies())
                finally:await ctx.close()
    asyncio.run(task())
