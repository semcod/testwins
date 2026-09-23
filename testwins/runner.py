from __future__ import annotations
import asyncio
import copy
import fnmatch
import importlib.metadata
import io
import json
import platform
import re
import uuid
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from PIL import Image, ImageDraw
from playwright.async_api import async_playwright, expect
from . import __version__
from .browser import launch, context_options
from .config import MATRICES
from .detectors import detect, from_axe
from .events import EventLog
from .model import Finding, identity
from .util import atomic_json, digest, origin, redact_url, utc_now, slug
from . import baseline
from .input import pointer,scroll_tile

COLLECTOR=Path(__file__).with_name("collector.js").read_text("utf-8")


def layout_signature(s: dict) -> str:
    return digest([(n["selector"],*[round(n["rect"][k],1) for k in ("x","y","width","height")])
                   for n in s["nodes"] if n["visibleRect"]["width"] and n["visibleRect"]["height"]] +
                  [(t.get("selector"),t.get("text")) for t in s["texts"]])


async def guard(context, cfg: dict) -> None:
    allowed={origin(cfg["base_url"]),*[origin(u) for u in cfg["allowed_origins"]]}
    async def route_handler(route):
        try:valid=origin(route.request.url) in allowed
        except ValueError:valid=route.request.url.startswith(("data:","blob:"))
        if valid:await route.continue_()
        else:await route.abort("blockedbyclient")
    await context.route("**/*",route_handler)
    if hasattr(context,"route_web_socket"):
        async def ws_handler(ws):
            u=re.sub(r"^ws", "http", ws.url)
            try: valid=origin(u) in allowed
            except ValueError: valid=False
            if valid:ws.connect_to_server()
            else:await ws.close()
        await context.route_web_socket("**/*",ws_handler)


async def collect(page, cdp, cfg: dict) -> dict:
    opts=dict(cfg["capture"]);opts["alignment"]=cfg["rules"]["alignment"];opts["capture_viewport"]=page.viewport_size
    if cdp:
        response=await cdp.send("Runtime.evaluate",{"expression":"("+COLLECTOR+")("+json.dumps(opts)+")",
                               "returnByValue":True,"awaitPromise":True})
        if response.get("exceptionDetails"):raise RuntimeError("rendered DOM collector failed")
        data=response.get("result",{}).get("value")
        if not isinstance(data,dict):raise RuntimeError("rendered DOM collector returned no data")
        return data
    return await page.evaluate(COLLECTOR,opts)


async def settle(page, cfg: dict) -> None:
    await page.locator(cfg["capture"]["ready_selector"]).first.wait_for(state="visible")
    await page.evaluate("() => Promise.race([document.fonts.ready,new Promise(r=>setTimeout(r,2000))])")
    await page.wait_for_timeout(cfg["capture"]["settle_ms"])


def paint(image_bytes: bytes, s: dict, findings: list[dict], image_path: Path, annotation: Path) -> None:
    image=Image.open(io.BytesIO(image_bytes)).convert("RGB")
    sx,sy=image.width/s["viewport"]["width"],image.height/s["viewport"]["height"]
    s["imageScale"]={"x":sx,"y":sy,"width":image.width,"height":image.height}
    draw=ImageDraw.Draw(image)
    def bounds(r):
        return (max(0,int(r["x"]*sx)),max(0,int(r["y"]*sy)),
                min(image.width,int((r["x"]+r["width"])*sx)),min(image.height,int((r["y"]+r["height"])*sy)))
    for r in s["masks"]:
        x0,y0,x1,y1=bounds(r)
        if x1>x0 and y1>y0:draw.rectangle((x0,y0,x1,y1),fill=(35,35,35))
    image.save(image_path)
    marked=image.copy();d=ImageDraw.Draw(marked)
    for i,f in enumerate(findings,1):
        for r in f["rects"]:
            x0,y0,x1,y1=bounds(r)
            if x1>x0 and y1>y0:
                d.rectangle((x0,y0,x1,y1),outline=(220,40,75),width=2)
                d.text((x0,max(0,y0-13)),str(i),fill=(220,40,75))
    marked.save(annotation)


async def assertion(page, spec: dict, previous: str, timeout_ms: int = 8000) -> None:
    kind=spec["kind"]
    if kind=="url":await expect(page).to_have_url(re.compile(spec["value"]))
    elif kind=="changed":
        await page.wait_for_function("old => document.body.innerText !== old",arg=previous)
    else:
        loc=page.locator(spec["selector"])
        if kind=="visible":await expect(loc).to_be_visible()
        elif kind=="hidden":await expect(loc).to_be_hidden()
        elif kind=="text":await expect(loc).to_have_text(spec["value"])
        elif kind=="count":await expect(loc).to_have_count(int(spec["value"]))
        elif kind=="contains_text":await expect(loc).to_contain_text(spec["value"])
        elif kind=="enabled":await expect(loc).to_be_enabled()
        elif kind=="disabled":await expect(loc).to_be_disabled()
        elif kind=="checked":await expect(loc).to_be_checked()
        elif kind=="unchecked":await expect(loc).not_to_be_checked()
        elif kind=="focused":await expect(loc).to_be_focused()
        elif kind=="value":await expect(loc).to_have_value(spec["value"])
        elif kind=="attribute":await expect(loc).to_have_attribute(spec["name"],spec["value"])
        elif kind=="count_min":
            deadline=asyncio.get_running_loop().time()+timeout_ms/1000
            while await loc.count()<spec["value"]:
                if asyncio.get_running_loop().time()>=deadline:raise AssertionError("Minimum count not reached")
                await page.wait_for_timeout(100)
        else:raise ValueError("Unhandled expectation")


async def act(page, s: dict, cdp=None, device=None, timeout_ms=8000) -> None:
    if s["action"]=="assert":return
    if s["action"]=="goto":
        await page.goto(s["value"],wait_until="domcontentloaded");return
    loc=page.locator(s["selector"])
    a="click" if s["action"]=="download" else s["action"]
    if cdp and a in ("click","hover","check"):
        if a=="check" and await loc.is_checked():return
        await pointer(page,cdp,s["selector"],touch=bool(device and device["touch"]),hover=a=="hover",timeout_ms=timeout_ms)
        if a=="check":await expect(loc).to_be_checked()
        return
    if a=="click":await loc.click()
    elif a=="fill":await loc.fill(s["value"])
    elif a=="press":await loc.press(s["key"])
    elif a=="hover":await loc.hover()
    elif a=="check":await loc.check()
    elif a=="select":await loc.select_option(s["value"])
    elif a=="scroll":await loc.scroll_into_view_if_needed()


async def discover(cfg: dict) -> list[dict]:
    """Bounded, opt-in DOM-link crawl. Even GET can mutate badly designed services: use disposable data."""
    c=cfg["crawl"]
    if not c["enabled"]:return cfg["routes"]
    routes=copy.deepcopy(cfg["routes"]);seen={r["path"] for r in routes};queue=list(routes)
    banned=re.compile(r"delete|logout|signout|unsubscribe|purchase|checkout|remove|reset",re.I)
    async with async_playwright() as pw:
        async with launch(pw,MATRICES[cfg["matrix"]][0],cfg) as (browser,_):
            ctx=await browser.new_context(**context_options(cfg,next(iter(cfg["devices"].values())),MATRICES[cfg["matrix"]][0]))
            await guard(ctx,cfg);page=await ctx.new_page()
            try:
                while queue and len(routes)<c["max_pages"]:
                    current=queue.pop(0)
                    await page.goto(urljoin(cfg["base_url"],current["path"]),wait_until="domcontentloaded",timeout=cfg["capture"]["timeout_ms"])
                    urls=await page.locator("a[href]").evaluate_all("xs => xs.map(x=>x.href)")
                    for url in sorted(set(urls)):
                        try:
                            if origin(url)!=origin(cfg["base_url"]):continue
                        except ValueError:continue
                        u=urlsplit(url);path=u.path+("?"+u.query if u.query else "")+("#"+u.fragment if u.fragment else "")
                        if path in seen or banned.search(path) or redact_url(url)!=url:continue
                        if not any(fnmatch.fnmatchcase(u.path,p) for p in c["allow_paths"]):continue
                        seen.add(path);r={"id":"crawl-"+digest(path)[:12],"path":path};routes.append(r);queue.append(r)
                        if len(routes)>=c["max_pages"]:break
            finally:await ctx.close()
    return routes


async def run(cfg: dict, output: Path) -> Path:
    cfg=copy.deepcopy(cfg)
    run_id=utc_now().replace(":","").replace(".","-")+"-"+uuid.uuid4().hex[:8]
    root=output/run_id;root.mkdir(parents=True,exist_ok=False)
    log=EventLog(root,run_id)
    config_hash=digest(cfg)
    # Do not persist journey values (they can be credentials), endpoints or absolute executable paths.
    public_cfg=copy.deepcopy(cfg)
    for journey in public_cfg["journeys"]:
        for step in journey["steps"]:
            if "value" in step:step["value"]="[REDACTED]"
            if "value" in step.get("expect",{}):step["expect"]["value"]="[OPERATOR EXPECTATION]"
    public_cfg["sessions"]={k:{"storage_state":"[PRIVATE LOCAL FILE]"} for k in cfg["sessions"]}
    public_cfg["base_url"]=redact_url(public_cfg["base_url"])
    public_cfg["cdp_endpoints"]={k:"[OPERATOR ENDPOINT]" for k in cfg["cdp_endpoints"]}
    atomic_json(root/"config.redacted.json",public_cfg)
    log.append("run_started",input_hash=config_hash,evidence=["config.redacted.json"],state="running")
    # Environment fingerprint contains runtime/package and installed-font metadata, not application data.
    import subprocess
    try:fonts=subprocess.run(["fc-list",":","family","style","file"],capture_output=True,text=True,timeout=5,check=True).stdout
    except (OSError,subprocess.SubprocessError):fonts="unavailable"
    render_environment=digest({"platform":platform.platform(),"playwright":importlib.metadata.version("playwright"),
                               "fonts":sorted(fonts.splitlines()),"image_id":__import__("os").environ.get("TW_IMAGE_ID","unrecorded")})
    snapshots=[];occurrences=[];cells=[];checks=[];run_gaps=[]
    try:cfg["routes"]=await discover(cfg)
    except Exception as e:
        run_gaps.append({"kind":"crawl_failure","exception_type":type(e).__name__})
    atomic_json(root/"route-inventory.json",cfg["routes"])
    scenes=[dict(r,steps=[]) for r in cfg["routes"]]+cfg["journeys"]
    from .gate import plan_checks
    cell_plan=[f"{b}-{d}" for b in MATRICES[cfg["matrix"]] for d in cfg["devices"]]
    check_plan=plan_checks(cfg,scenes,cell_plan)
    checks=[dict(c,status="not_run") for c in check_plan]
    check_index={(c["cell"],c["repeat"],c["scene"],c["step"]):c for c in checks}
    axe_code=None
    if cfg["axe"]["enabled"] and Path(cfg["axe"]["path"]).is_file():axe_code=Path(cfg["axe"]["path"]).read_text("utf-8")

    async def capture(page,cdp,bname,dname,device,version,transport,stage,repeat,extra=None):
        await settle(page,cfg)
        before=await collect(page,cdp,cfg)
        png=await page.screenshot(type="png",full_page=False,scale="css",animations="disabled" if cfg["capture"]["freeze_animations"] else "allow")
        s=await collect(page,cdp,cfg)
        stable=layout_signature(before)==layout_signature(s)
        if not stable:
            await asyncio.sleep(0.2)
            png=await page.screenshot(type="png",full_page=False,scale="css",animations="disabled" if cfg["capture"]["freeze_animations"] else "allow")
            s_retry=await collect(page,cdp,cfg)
            if layout_signature(s)==layout_signature(s_retry):
                s=s_retry;stable=True
        s["stable"]=stable;s["url"]=redact_url(page.url)
        s["links"]=[redact_url(x) for x in s["links"]]
        findings=detect(s,cfg,device)+(extra or [])
        if not stable:
            s["gaps"].append({"kind":"unstable_layout","reason":"Layout moved between DOM and screenshot observations."})
            for f in findings:f["candidate"]=True;f["confidence"]=min(f["confidence"],.6)
        if s["truncated"]:s["gaps"].append({"kind":"capture_limit","reason":"DOM/text/HTML capture limit reached."})
        if s["fontsStatus"]!="loaded":s["gaps"].append({"kind":"fonts_pending","reason":"Fonts did not settle before capture."})
        axe_status="disabled"
        axe_data=None
        if cfg["axe"]["enabled"]:
            if not axe_code:
                axe_status="unavailable"
                if cfg["axe"]["required"]:s["gaps"].append({"kind":"required_detector_missing","reason":"axe-core asset is unavailable."})
            else:
                try:
                    await page.evaluate(axe_code)
                    axe_data=await asyncio.wait_for(page.evaluate("async masks => {const r=await axe.run({exclude:masks.map(s=>[s])},{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}});return {violations:r.violations.map(v=>({id:v.id,impact:v.impact,help:v.help,helpUrl:v.helpUrl,nodes:v.nodes.map(n=>({target:n.target}))})),incomplete:r.incomplete.map(x=>x.id)};}",cfg["capture"]["mask_selectors"]),30)
                    findings+=from_axe(axe_data);axe_status="completed"
                except Exception:
                    axe_status="error"
                    if cfg["axe"]["required"]:s["gaps"].append({"kind":"required_detector_failed","reason":"axe-core did not complete."})
        folder=Path("evidence")/f"{bname}-{dname}"/f"r{repeat}"/slug(stage)
        dest=root/folder;dest.mkdir(parents=True,exist_ok=True)
        html=s.pop("html")
        (dest/"rendered.html").write_text(html,"utf-8")
        image_path=dest/"viewport.png";annotation=dest/"annotated.png"
        paint(png,s,findings,image_path,annotation)
        meta={"project":cfg["project"],"browser":bname,"browser_version":version,"transport":transport,
              "device":dname,"stage":stage,"viewport_profile":device,"locale":cfg["locale"],
              "timezone":cfg["timezone"],"color_scheme":cfg["color_scheme"],"url":redact_url(page.url),
              "render_environment":render_environment,"mobile_emulation":bool(device["mobile"] and bname!="firefox"),"tool_version":__version__}
        bfind,bstatus=baseline.assess(image_path,meta,cfg,dest/"diff.png");findings+=bfind
        if bstatus.startswith("incompatible"):s["gaps"].append({"kind":"baseline_incompatible","reason":bstatus})
        atomic_json(dest/"snapshot.json",s);atomic_json(dest/"meta.json",meta)
        if axe_data is not None:atomic_json(dest/"axe.json",axe_data)
        evidence=[str(folder/x) for x in ("viewport.png","snapshot.json","rendered.html","meta.json")]
        ss={"meta":meta,"image":evidence[0],"data":evidence[1],"html":evidence[2],
            "annotation":str(folder/"annotated.png"),"stable":stable,"baseline":bstatus,
            "axe":axe_status,"gaps":s["gaps"],"repeat":repeat}
        from .performance import measure
        ss["performance"]=await measure(cdp,cfg["performance"])
        if ss["performance"]["status"]=="incomplete":
            ss["gaps"].append({"kind":"required_performance_missing","reason":"Configured CDP budget could not be observed"})
        atomic_json(dest/"performance.json",ss["performance"])
        evidence.append(str(folder/"performance.json"))
        snapshots.append(ss)
        for f in findings:
            occurrences.append(dict(f,fingerprint=identity(cfg["project"],stage,f),
                                     cell=f"{bname}-{dname}",repeat=repeat,stage=stage,
                                     stable=stable,evidence=evidence))
        log.append("snapshot_recorded",input_hash=config_hash,evidence=evidence,
                   state="observed",outcome="OBSERVED")
        return s

    async def run_cell(browser,bname,dname,device,version,transport,cell):
        for repeat in range(1,cfg["capture"]["repeats"]+1):
            for scene in scenes:
                context=None
                try:
                    context=await browser.new_context(**context_options(cfg,device,bname,scene))
                    await guard(context,cfg)
                    page=await context.new_page();page.set_default_timeout(cfg["capture"]["timeout_ms"])
                    page.set_default_navigation_timeout(cfg["capture"]["timeout_ms"])
                    expect.set_options(timeout=cfg["capture"]["timeout_ms"])
                    cdp=await context.new_cdp_session(page) if transport=="cdp" else None
                    if cdp and cfg["performance"]["enabled"]:await cdp.send("Performance.enable")
                    if scene.get("setup_path"):
                        await page.goto(urljoin(cfg["base_url"],scene["setup_path"]),wait_until="domcontentloaded")
                        await settle(page,cfg)
                    await page.goto(urljoin(cfg["base_url"],scene["path"]),wait_until="domcontentloaded")
                    if cfg["capture"]["freeze_animations"]:
                        await page.add_style_tag(content="*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important;scroll-behavior:auto!important}")
                        await page.evaluate("() => { if(!window.__tw_instant){window.__tw_instant=true;const orig=Element.prototype.scrollIntoView;Element.prototype.scrollIntoView=function(a){if(a&&typeof a==='object'&&a.behavior==='smooth')a=Object.assign({},a,{behavior:'instant'});return orig.call(this,a);};} }")
                    await capture(page,cdp,bname,dname,device,version,transport,scene["id"]+"--initial",repeat)
                    cell["observed_scenes"]+=1
                    if not scene.get("steps"):
                        last_y=0
                        for tile in range(1,cfg["capture"]["scroll_tiles"]):
                            y=await scroll_tile(page,cdp,device)
                            if abs(y-last_y)<1:break
                            last_y=y
                            await capture(page,cdp,bname,dname,device,version,transport,scene["id"]+f"--scroll-{tile}",repeat)
                    failed=False
                    for step in scene.get("steps",[]):
                        check=check_index[(cell["id"],repeat,scene["id"],step["id"])]
                        if failed:continue
                        if cfg["capture"]["before_steps"]:
                            await capture(page,cdp,bname,dname,device,version,transport,scene["id"]+"--"+step["id"]+"--before",repeat)
                            check["before"]=snapshots[-1]["image"]
                        previous=await page.locator("body").inner_text() if step["expect"]["kind"]=="changed" else ""
                        error=[];action_completed=False
                        try:
                            action=dict(step)
                            if action["action"]=="goto":action["value"]=urljoin(cfg["base_url"],action["value"])
                            if step["action"]=="download":
                                from .downloads import inspect_download
                                async with page.expect_download(timeout=cfg["capture"]["timeout_ms"]) as pending:
                                    await act(page,action,cdp,device,cfg["capture"]["timeout_ms"])
                                    action_completed=True
                                download=await pending.value
                                location=Path("evidence")/cell["id"]/f"r{repeat}"/slug(scene["id"]+"--"+step["id"])/"download"
                                check["download_evidence"]=str(location/"download.json")
                                check["download"]=await asyncio.wait_for(inspect_download(download,step["expect"],cfg["downloads"],root/location),cfg["capture"]["timeout_ms"]/1000)
                            else:
                                await act(page,action,cdp,device,cfg["capture"]["timeout_ms"])
                                action_completed=True
                                await assertion(page,step["expect"],previous,cfg["capture"]["timeout_ms"])
                            check["status"]="passed"
                        except Exception as exc:
                            failed=True;check["status"]="failed" if action_completed else "blocked";check["exception_type"]=type(exc).__name__
                            error=[Finding("TW-FUNCTION-ASSERTION" if action_completed else "TW-ACTION-UNVERIFIED",
                                  "Brak oczekiwanego rezultatu w interfejsie" if action_completed else "Nie udało się wykonać działania UI",
                                  f"Scenariusz {scene['id']}, krok {step['id']}: działanie lub jawna asercja UI nie powiodły się.",
                                  [step.get("selector") or step["expect"].get("selector","page")],[],"high",.99,
                                  not action_completed or step["expect"]["kind"]=="changed",{"action":step["action"],"action_completed":action_completed,"expectation_kind":step["expect"]["kind"]}).to_dict()]
                        await capture(page,cdp,bname,dname,device,version,transport,scene["id"]+"--"+step["id"],repeat,error)
                        check["after"]=snapshots[-1]["image"]
                except Exception as exc:
                    cell["errors"].append({"scene":scene["id"],"repeat":repeat,"exception_type":type(exc).__name__,"message":str(exc),"code":"TW-CAPTURE-FAILED"})
                finally:
                    if context:await context.close()

    async def browser_worker(pw,bname):
        local=[]
        for dname,device in cfg["devices"].items():
            cell={"id":f"{bname}-{dname}","browser":bname,"device":dname,"version":None,
                  "transport":"cdp" if bname in ("chromium","chrome","edge","brave") else "playwright",
                  "errors":[],"observed_scenes":0,"expected_scenes":len(scenes)*cfg["capture"]["repeats"]}
            cells.append(cell);local.append((dname,device,cell))
        try:
            async with launch(pw,bname,cfg) as (browser,transport):
                for dname,device,cell in local:
                    cell["version"]=browser.version
                    try:await asyncio.wait_for(run_cell(browser,bname,dname,device,browser.version,transport,cell),cfg["capture"]["max_cell_seconds"])
                    except Exception as e:cell["errors"].append({"code":"TW-CELL-FAILED","exception_type":type(e).__name__,"message":str(e)})
        except Exception as e:
            for _,_,cell in local:cell["errors"].append({"code":"TW-BROWSER-UNAVAILABLE","exception_type":type(e).__name__,"message":str(e)})

    async with async_playwright() as pw:
        await asyncio.gather(*(browser_worker(pw,b) for b in MATRICES[cfg["matrix"]]))
    from .reporting import finalize
    data={"schema":"testwins.report/v1","run_id":run_id,"created":utc_now(),"project":cfg["project"],
          "tool_version":__version__,"config_hash":config_hash,"matrix":cfg["matrix"],
          "environment":{"platform":platform.platform(),"playwright":importlib.metadata.version("playwright"),
                         "sandbox_enabled":cfg["sandbox"],"headless":cfg["headless"],"fixture_mode":__import__("os").environ.get("TW_VERIFICATION_FIXTURE","none")},
          "cell_plan":cell_plan,"check_plan":check_plan,"cells":cells,"snapshots":snapshots,"occurrences":occurrences,"checks":checks,"run_gaps":run_gaps}
    finalize(root,data,cfg)
    log.append("run_completed",input_hash=config_hash,evidence=["report.json","manifest.json","proposals.json"],
               outcome="SUCCEEDED" if data["gate"]["exit_code"]==0 else "FAILED",state="finished")
    atomic_json(output/"latest.json",{"run_id":run_id,"directory":run_id})
    return root
