"""Real frame hit tests, cropped screenshots, privacy and honest missing scope."""
import asyncio
import html
import io
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image
from playwright.async_api import Page, async_playwright

from testwins.config import load, validate
from testwins.frames import resolve
from testwins.runner import act, collect, paint, run, capture_observation
from testwins.verification import verify_run

pytestmark=pytest.mark.browser
CHILD='''<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{margin:0;background:white}button{position:absolute;left:20px;top:20px;width:100px;height:40px}
#private{position:absolute;left:20px;top:90px;width:120px;height:35px;background:red;color:white}</style>
<button id="go" onclick="this.textContent=event.isTrusted?'Clicked':'Untrusted'">Ready</button>
<div id="private" data-private>FRAME SECRET</div>'''


def markup(child=CHILD):
    return '<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;min-height:400px}iframe{position:absolute;left:40px;top:50px;width:280px;height:180px;border:4px solid blue}</style><iframe id="guide" srcdoc="'+html.escape(child,quote=True)+'"></iframe>'


def config(touch=False):
    cfg=load();cfg.update(matrix='chromium',headless=True)
    cfg['devices']={'desktop':dict(width=400,height=400,dpr=1,touch=touch,mobile=False)}
    cfg['capture'].update(repeats=1,scroll_tiles=1,settle_ms=0,ready_selector='body')
    cfg['axe']['enabled']=False
    cfg['frames']=[{'id':'guide','selector':'#guide'}];cfg['routes'][0]['frames']=['guide']
    if os.environ.get('CHROMIUM_EXECUTABLE'):cfg['executables']['chromium']=os.environ['CHROMIUM_EXECUTABLE']
    return validate(cfg)


@pytest.mark.parametrize('touch',[False,True])
def test_frame_pixels_masks_and_trusted_input_use_child_coordinates(tmp_path,touch):
    async def check():
        async with async_playwright() as pw:
            browser=await pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_EXECUTABLE'),headless=True,args=['--no-sandbox'])
            page=await browser.new_page(viewport={'width':400,'height':400},has_touch=touch)
            await page.set_content(markup())
            cfg=config(touch);surface=await resolve(page,cfg,'guide')
            await act(surface,{'action':'click','selector':'#go'},device=cfg['devices']['desktop'])
            assert await surface.locator('#go').inner_text()=='Clicked'
            await act(surface,{'action':'press','selector':'#go','key':'Tab'})
            png,snapshot=await capture_observation(surface,None,cfg)
            assert snapshot['scope']['parent_rect']==dict(x=44,y=54,width=280,height=180)
            assert next(n for n in snapshot['nodes'] if n['selector']=='#go')['rect']['x']==20
            assert 'FRAME SECRET' not in json.dumps(snapshot)
            assert Image.open(io.BytesIO(png)).size==(280,180)
            paint(png,snapshot,[],tmp_path/'frame.png',tmp_path/'marked.png')
            assert Image.open(tmp_path/'frame.png').getpixel((25,95))==(35,35,35)
            root=await collect(page,None,cfg)
            paint(await page.screenshot(scale='css'),root,[],tmp_path/'root.png',tmp_path/'root-marked.png')
            assert Image.open(tmp_path/'root.png').getpixel((70,80))==(35,35,35)
            await browser.close()
    asyncio.run(check())


@pytest.mark.parametrize('mutation',[
    "document.querySelector('iframe').setAttribute('data-private','')",
    "document.querySelector('iframe').style.transform='scale(.8)'",
    "document.querySelector('iframe').style.top='350px'",
    "document.body.insertAdjacentHTML('beforeend','<div style=\"position:absolute;inset:0;background:red\"></div>')",
    "document.body.append(document.querySelector('iframe').cloneNode(true))",
    "document.querySelector('iframe').setAttribute('srcdoc','');document.querySelector('iframe').setAttribute('sandbox','');document.querySelector('iframe').srcdoc='<p>opaque</p>'",
])
def test_unsupported_or_private_frames_never_claim_complete(tmp_path,mutation):
    async def fixture(page,url,**kwargs):
        await page.set_content(markup());await page.evaluate(mutation);await page.wait_for_timeout(60)
    with patch.object(Page,'goto',fixture):root=asyncio.run(run(config(),tmp_path))
    verify_run(root)
    report=json.loads((root/'report.json').read_text())
    assert report['gate']['exit_code']==2
    assert any(g['kind']=='frame_unavailable' for s in report['snapshots'] for g in s['gaps'])
    assert not any(s['meta']['scope']['kind']=='frame' for s in report['snapshots'])


@pytest.mark.parametrize('has_nested',[False,True])
def test_journey_records_separate_scopes_and_keeps_nested_gaps(tmp_path,has_nested):
    nested=CHILD+('<iframe style="position:absolute;left:170px;top:90px;width:50px;height:50px" srcdoc="NESTED SECRET"></iframe>' if has_nested else '')
    async def fixture(page,url,**kwargs):await page.set_content(markup(nested))
    cfg=config();cfg['routes']=[];cfg['journeys']=[{'id':'read','path':'/','frames':['guide'],'steps':[
        {'id':'click','frame':'guide','action':'click','selector':'#go','allow_mutation':True,
         'expect':{'kind':'text','selector':'#go','value':'Clicked'}}]}]
    with patch.object(Page,'goto',fixture):root=asyncio.run(run(validate(cfg),tmp_path))
    verify_run(root);report=json.loads((root/'report.json').read_text())
    assert report['checks'][0]['status']=='passed'
    assert report['checks'][0]['scope']['id']=='guide'
    roots=[s for s in report['snapshots'] if s['meta']['scope']['kind']=='root']
    children=[s for s in report['snapshots'] if s['meta']['scope']['kind']=='frame']
    assert len(roots)==len(children)==3
    assert all(not s['gaps'] for s in roots)
    assert all(any(g['kind']=='frame_nested' for g in s['gaps']) == has_nested for s in children)
    assert report['gate']['exit_code']==(2 if has_nested else 0)
    for s in report['snapshots']:
        assert 'SECRET' not in (root/s['html']).read_text()
        assert 'SECRET' not in (root/s['data']).read_text()


def test_cross_origin_is_rejected_even_when_network_origin_is_allowed(tmp_path):
    async def fixture(page,url,**kwargs):
        async def respond(route):
            body=markup().replace('srcdoc="'+html.escape(CHILD,quote=True)+'"','src="http://child.test/frame"') if route.request.url.startswith('http://sut:8080') else CHILD
            await route.fulfill(content_type='text/html',body=body)
        await page.route('**/*',respond)
        await original(page,url,**kwargs)
    original=Page.goto;cfg=config();cfg['allowed_origins']=['http://child.test']
    with patch.object(Page,'goto',fixture):root=asyncio.run(run(validate(cfg),tmp_path))
    report=json.loads((root/'report.json').read_text())
    assert report['gate']['exit_code']==2
    assert any(g['kind']=='frame_unavailable' for s in report['snapshots'] for g in s['gaps'])
    assert all(s['meta']['scope']['kind']=='root' for s in report['snapshots'])
    assert 'FRAME SECRET' not in ''.join(p.read_text() for p in root.rglob('snapshot.json'))


def test_frame_pixels_stay_masked_after_capture_limit(tmp_path):
    async def fixture(page,url,**kwargs):
        await page.set_content(markup().replace('<iframe', '<div>'+('<p>Public</p>'*30)+'</div><iframe'))
    cfg=config();cfg['frames']=[];cfg['routes'][0]['frames']=[];cfg['capture']['max_elements']=10
    with patch.object(Page,'goto',fixture):root=asyncio.run(run(cfg,tmp_path))
    report=json.loads((root/'report.json').read_text());assert report['gate']['exit_code']==2
    image=Image.open(root/report['snapshots'][0]['image'])
    assert image.getpixel((70,150))==(35,35,35)
