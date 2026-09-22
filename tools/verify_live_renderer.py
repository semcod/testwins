#!/usr/bin/env python3
"""Persist evidence from actual Chromium/CDP on OWNED INLINE fixtures, not HTTP E2E."""
from __future__ import annotations
import argparse
import asyncio
import importlib.util
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from testwins.config import load
from testwins.live.config import WatchConfig,Target
from testwins.live.scanner import BrowserScanner,OBSERVER
from testwins.live.store import Store
from testwins.live.export import export
from testwins.util import atomic_json,file_digest

async def run(output:Path):
    if output.exists():raise ValueError('Choose a new output directory')
    output.mkdir(parents=True)
    fixture=Path(__file__).resolve().parents[1]/'tests/live/test_renderer_live.py'
    spec=importlib.util.spec_from_file_location('controlled_fixture',fixture);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    audit=load();exe=shutil.which('chromium')
    if not exe:raise RuntimeError('System Chromium required for this verification helper')
    audit['executables']={'chromium':exe};audit['headless']=True;audit['axe']['enabled']=False;audit['rules']['heuristic_alignment']=False
    audit['capture']['settle_ms']=30;audit['capture']['timeout_ms']=1000
    targets=[Target(f'fixture:home:chromium:{d}','fixture','http://unused.invalid/','home',device=d,hot=True,audit=audit,
         expect=({'kind':'visible','selector':'#ok'},)) for d in ['desktop','tablet','mobile']]
    root=output/'live';cfg=WatchConfig('renderer-proof',targets,root,output,max_hot_pages=3,repeat_gap_s=.05,css_provenance=True)
    store=Store(root/'live.sqlite');scanner=BrowserScanner(cfg);results=[]
    await scanner.start()
    try:
        for t in targets:
            _,page,_,_,_=await scanner._page(t);await page.set_content(m.DIRTY);await page.evaluate(OBSERVER)
            for repeat in range(2):
                r=await scanner.scan(t,2,'dom');store.record(t.id,t.scope,r);results.append(r)
                assert r['transport']=='cdp';assert r['status']=='complete',r['gaps']
                if repeat==0:shutil.copyfile(root/r['evidence']/'annotated.png',output/f'defects-{t.device}.png')
        before=store.status(all_incidents=True);atomic_json(output/'before.json',before)
        assert before['totals'].get('confirmed',0)>=9
        proposal=export(store,root,output/'confirmed-export','renderer-proof')
        # Render the real dashboard with a frozen, explicitly labelled verification state.
        dashboard=Path(__file__).resolve().parents[1]/'testwins/live/dashboard.html'
        html=dashboard.read_text();head=html[:html.index("$('filter').addEventListener")]
        html=head+"state="+json.dumps(before,ensure_ascii=False).replace('<','\\u003c')+"; render(); $('stream').textContent='Migawka weryfikacyjna, nie live';</script></html>"
        browser,_=await scanner._browser(targets[0]);ctx=await browser.new_context(viewport={'width':1440,'height':1000})
        page=await ctx.new_page();await page.set_content(html);await page.screenshot(path=str(output/'dashboard.png'),full_page=True);await ctx.close()
        for t in targets:
            _,page,_,_,_=await scanner._page(t);await page.set_content(m.CLEAN)
            for _ in range(3):
                r=await scanner.scan(t,2,'dom');store.record(t.id,t.scope,r);results.append(r)
        after=store.status(all_incidents=True);atomic_json(output/'after.json',after)
        assert after['totals'].get('confirmed',0)==0
        events=store.events(0,1000);atomic_json(output/'events.json',events)
        summary={'mode':'real Chromium/CDP + owned inline HTML; NO HTTP navigation, policies unchanged',
          'playwright':importlib.metadata.version('playwright'),'chromium':results[0]['browser_version'],
          'devices':[t.device for t in targets],'scans':len(results),'complete_scans':sum(r['status']=='complete' for r in results),
          'confirmed_before':before['totals'].get('confirmed',0),'confirmed_after':after['totals'].get('confirmed',0),
          'resolved_after':after['totals'].get('resolved',0),'proposals':proposal['proposals'],
          'rules':sorted({f['rule'] for r in results for f in r['findings']}),
          'css_provenance_bundles':len(list(root.glob('evidence/*/rendered-css.json'))),
          'sdk_planfile_called':False,'llm_called':False,'docker_used':False}
        atomic_json(output/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))
    finally:
        await scanner.close();store.close()
    atomic_json(output/'SHA256.json',{str(p.relative_to(output)):file_digest(p) for p in output.rglob('*') if p.is_file()})

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();asyncio.run(run(a.output.resolve()))
