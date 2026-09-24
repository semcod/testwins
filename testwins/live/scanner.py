from __future__ import annotations
import asyncio
import copy
import hashlib
import io
import json
import time
import uuid
from contextlib import AsyncExitStack
from pathlib import Path
from PIL import Image,ImageChops,ImageStat
from ..browser import launch,context_options
from ..runner import capture_observation,settle,guard,paint
from ..detectors import detect,from_axe
from ..util import atomic_json,redact_url,file_digest,digest
from ..model import Finding
from .diagnosis import enrich,supplementary,BY_RULE

OBSERVER=Path(__file__).with_name('observer.js').read_text('utf-8')
BASE_RULES={'TW-OVERLAY-CONTRACT','TW-TEXT-OVERLAP','TW-TEXT-CLIPPED','TW-VIEWPORT-OVERFLOW','TW-VIEWPORT-META','TW-CONTROL-OCCLUDED',
  'TW-TARGET-SMALL','TW-ALIGNMENT','TW-ALIGNMENT-CANDIDATE','TW-POINTER-DISABLED','TW-FOCUS-OBSCURED',
  'TW-ARIA-HIDDEN-FOCUS','TW-EMPTY-UI','TW-TEXT-SMALL','TW-FONT-PENDING','TW-LAYOUT-UNSTABLE','TW-IMAGE-BROKEN','TW-EXPECTATION'}


class BrowserScanner:
    """Reused browser processes; bounded, opt-in hot contexts; no user's default profile."""
    def __init__(self,cfg):
        self.cfg=cfg;self.stack=AsyncExitStack();self.pw=None;self.browsers={};self.hot={};self.last_revision={};self.previous_pixels={}
        self.start_lock=asyncio.Lock();self.restarts=0;self.browser_managers={}
    async def start(self):
        from playwright.async_api import async_playwright
        self.pw=await self.stack.enter_async_context(async_playwright())
    async def close(self):
        for ctx,page,*_ in list(self.hot.values()):
            try:await ctx.close()
            except Exception:pass
        self.hot.clear()
        for manager in list(self.browser_managers.values()):
            try:await manager.__aexit__(None,None,None)
            except Exception:pass
        self.browser_managers.clear();await self.stack.aclose()
    async def _browser(self,t):
        # Browser processes may be shared; each target has an isolated incognito context.
        key=t.browser
        async with self.start_lock:
            current=self.browsers.get(key)
            if current and current[0].is_connected():return current
            if current:
                self.restarts+=1
                old=self.browser_managers.pop(key,None)
                if old:await old.__aexit__(None,None,None)
            manager=launch(self.pw,t.browser,t.audit)
            pair=await manager.__aenter__();self.browser_managers[key]=manager
            self.browsers[key]=pair;return pair
    async def _page(self,t):
        if t.id in self.hot:
            ctx,page,session,transport=self.hot[t.id]
            if not page.is_closed():return ctx,page,session,transport,False
            self.hot.pop(t.id,None)
        browser,transport=await self._browser(t)
        ctx=await browser.new_context(**context_options(t.audit,t.audit['devices'][t.device],t.browser))
        try:
            await guard(ctx,t.audit)
            await ctx.add_init_script('('+OBSERVER+')()')
            page=await ctx.new_page();page.set_default_timeout(t.audit['capture']['timeout_ms'])
            session=await ctx.new_cdp_session(page) if transport=='cdp' else None
            if t.hot and len(self.hot)<self.cfg.max_hot_pages:self.hot[t.id]=(ctx,page,session,transport)
            return ctx,page,session,transport,True
        except BaseException:
            await ctx.close();raise
    async def dirty(self):
        result=[]
        for tid,(ctx,page,session,transport) in list(self.hot.items()):
            try:
                state=await asyncio.wait_for(page.evaluate('window.__testwins_live_v1?.revision ?? 0'),.5)
                previous=self.last_revision.get(tid,state);self.last_revision[tid]=state
                if previous!=state:result.append(tid)
            except Exception:pass
        return result
    async def scan(self,t,tier=1,reason='periodic'):
        started=time.monotonic();ctx=None;dest=None
        result={'status':'incomplete','findings':[],'covered_rules':[],'gaps':[], 'tier':tier,'evidence':'',
                'browser':t.browser,'device':t.device,'site':t.site,'route':t.route,'url':redact_url(t.url),'trigger':reason}
        try:
            ctx,page,cdp,transport,new=await self._page(t)
            # A hot page's periodic navigation catches server-side changes without HMR.
            if new or reason!='dom':
                await page.goto(t.url,wait_until='domcontentloaded',timeout=t.audit['capture']['timeout_ms'])
            if tier==0:
                result['status']='limited';result['gaps']=[{'kind':'tier_limit','reason':'L0 heartbeat only; GUI rules not evaluated'}]
                return result
            await settle(page,t.audit)
            png,s=await capture_observation(page,cdp,t.audit,retries=0,repeat_gap_s=self.cfg.repeat_gap_s)
            stable=s['stable'];result['stability']=s['stability']
            s['url']=redact_url(page.url);s['links']=[redact_url(u) for u in s.get('links',[])]
            result['transport']=transport;result['browser_version']=(await self._browser(t))[0].version
            f=detect(s,t.audit,t.audit['devices'][t.device])+supplementary(s,stable=stable)
            # Read-only contracts: no action, shell command or generated JS from web content.
            for e in t.expect:
                loc=page.locator(e['selector'])
                kind=e['kind'];count=await loc.count()
                ok=(await loc.first.is_visible() if count else False) if kind=='visible' else (not count or not await loc.first.is_visible()) if kind=='hidden' else count==e['value'] if kind=='count' else count==1 and (await loc.inner_text()).strip()==e['value']
                if not ok:f.append(Finding('TW-EXPECTATION','Niespełniony kontrakt obserwowanego stanu',f"Oczekiwanie {kind} nie zostało spełnione.",[e['selector']],[],e.get('severity','high'),.97,details={'kind':kind,'value':'[OPERATOR EXPECTATION]','contract_id':digest(e)[:16]}).to_dict())
            gaps=list(s.get('gaps',[]))
            if s.get('truncated'):gaps.append({'kind':'capture_limit'})
            if not stable:gaps.append({'kind':'unstable_layout','layout_stable':s['stability']['layout'],
                                       'state_stable':s['stability']['state']})
            # DOM completeness for supported light/open-shadow surfaces. iframe/canvas gaps remain explicit.
            if not s.get('truncated') and stable and not any(g.get('kind') in {'detector_limit','alignment_contract','overlay_contract'} for g in gaps):
                result['covered_rules']=sorted(BASE_RULES)
            else:
                for ff in f:ff['candidate']=True
            if tier>=2 and t.audit['axe']['enabled']:
                asset=Path(t.audit['axe']['path'])
                if asset.is_file():
                    try:
                        await page.evaluate(asset.read_text('utf-8'))
                        axe=await asyncio.wait_for(page.evaluate("async masks=>{const r=await axe.run({exclude:masks.map(s=>[s])}); return {violations:r.violations.map(v=>({id:v.id,help:v.help,impact:v.impact,helpUrl:v.helpUrl,nodes:v.nodes.map(n=>({target:n.target}))})),passes:r.passes.map(p=>p.id),incomplete:r.incomplete.map(i=>i.id)}}",t.audit['capture']['mask_selectors']),20)
                        f+=from_axe(axe)
                        result['covered_rules']+=['TW-AXE-'+rid.upper() for rid in axe['passes']+[v['id'] for v in axe['violations']] if rid not in axe['incomplete']]
                        if axe['incomplete']:gaps.append({'kind':'axe_incomplete','rules':axe['incomplete']})
                    except Exception as exc:gaps.append({'kind':'axe_error','exception_type':type(exc).__name__})
                else:gaps.append({'kind':'axe_unavailable','required':t.audit['axe']['required']})
            elif t.audit['axe']['enabled']:gaps.append({'kind':'tier_limit','reason':'axe not evaluated at L1'})
            dest=self.cfg.output/'evidence'/('scan-'+uuid.uuid4().hex)
            dest.mkdir(parents=True,exist_ok=False)
            html=s.pop('html','')
            # Rendered semantic HTML can still contain application text; remains local.
            (dest/'rendered.html').write_text(html,encoding='utf-8')
            paint(png,s,f,dest/'viewport.png',dest/'annotated.png')
            if tier>=2:
                # A rolling reference is a change detector, never an approved visual baseline.
                image=Image.open(dest/'viewport.png').convert('RGB').resize((96,64))
                key=t.id+':'+t.scope
                previous=self.previous_pixels.get(key)
                if previous is not None:
                    score=sum(ImageStat.Stat(ImageChops.difference(image,previous)).mean)/(3*255)
                    if score>.035:
                        f.append(Finding('TW-PIXEL-DRIFT','Obraz zmienił się od poprzedniego pomiaru',
                          'Zmiana wymaga oceny zamiaru; poprzedni obraz nie jest zaakceptowanym baseline.', ['html'],[], 'normal',.55,True,{'normalized_difference':score}).to_dict())
                self.previous_pixels[key]=image
                result['covered_rules'].append('TW-PIXEL-DRIFT')
            result['findings']=[enrich(ff,s) for ff in f]
            if self.cfg.css_provenance and tier>=2 and f:
                from .provenance import inspect
                try:
                    provenance=await inspect(cdp,[sel for ff in f for sel in ff.get('selectors',[])])
                    atomic_json(dest/'rendered-css.json',provenance)
                    for ff in result['findings']:
                        ff['diagnosis']['rendered_css']=[n for n in provenance['nodes'] if n['selector'] in ff['selectors']]
                except Exception as exc:gaps.append({'kind':'css_provenance_unavailable','exception_type':type(exc).__name__})
            result['gaps']=gaps
            result['status']='complete' if not gaps else 'partial'
            result['scope_notes']=['visible viewport only','no mutation actions','no HTTP/API or source-code diagnosis','closed shadow roots not enumerated',
                                   'no accessibility scan' if not t.audit['axe']['enabled'] else 'axe requested']
            atomic_json(dest/'snapshot.json',s)
            result['evidence']=str(dest.relative_to(self.cfg.output))
            result['image_sha256']=file_digest(dest/'viewport.png')
            result['dom_sha256']=file_digest(dest/'snapshot.json')
            try:self.last_revision[t.id]=await page.evaluate('window.__testwins_live_v1?.revision ?? 0')
            except Exception:pass
            return result
        except asyncio.CancelledError:
            self.hot.pop(t.id,None)
            raise
        except Exception as exc:
            # Never echo SUT contents, URLs, session tokens or entire Playwright exception messages.
            result['gaps'].append({'kind':'scan_failed','exception_type':type(exc).__name__})
            if t.id in self.hot:self.hot.pop(t.id,None)
            return result
        finally:
            result['duration_s']=round(time.monotonic()-started,4)
            if dest:
                atomic_json(dest/'scan.json',result)
                hashes={p.name:file_digest(p) for p in dest.iterdir() if p.is_file()}
                atomic_json(dest/'manifest.json',{'schema':'testwins.live-evidence/v1','authority':'none','sha256':hashes})
            if ctx and t.id not in self.hot:
                try:await ctx.close()
                except Exception:pass
