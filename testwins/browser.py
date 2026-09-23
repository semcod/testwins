from __future__ import annotations
import asyncio
import os
import shutil
import subprocess
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Any

CDP_BROWSERS={"chromium","chrome","edge","brave"}
CANDIDATES={"chrome":["google-chrome","google-chrome-stable"],
            "edge":["microsoft-edge","microsoft-edge-stable"],"brave":["brave-browser"]}


def browser_env() -> dict[str,str]:
    # Do not hand local LLM, cloud or repository credentials to browser children.
    allowed={"PATH","HOME","DISPLAY","LANG","LC_ALL","XDG_RUNTIME_DIR","DBUS_SESSION_BUS_ADDRESS",
             "LD_LIBRARY_PATH","FONTCONFIG_PATH","PLAYWRIGHT_BROWSERS_PATH","TMPDIR"}
    return {k:v for k,v in os.environ.items() if k in allowed}


@asynccontextmanager
async def launch(pw: Any, name: str, cfg: dict) -> AsyncIterator[tuple[Any,str]]:
    browser=None; process=None; profile=None; logfile=None; external=False
    try:
        if name in CDP_BROWSERS:
            endpoint=cfg["cdp_endpoints"].get(name)
            if endpoint:
                # Only operator-supplied endpoints; never reuse the host user's profile automatically.
                external=True
            else:
                exe=cfg["executables"].get(name)
                if not exe:
                    if name=="chromium":
                        exe=pw.chromium.executable_path if Path(pw.chromium.executable_path).exists() else next((shutil.which(x) for x in ("chromium","google-chrome","google-chrome-stable","chromium-browser") if shutil.which(x)),None)
                    else:
                        exe=next((shutil.which(x) for x in CANDIDATES[name] if shutil.which(x)),None)
                if not exe or not Path(exe).exists():raise RuntimeError(f"browser unavailable: {name} (binary not found; run 'playwright install {name}' or configure in cfg['executables'])")
                profile=Path(tempfile.mkdtemp(prefix="testwins-"+name+"-"))
                logfile=(profile/"launcher.log").open("wb")
                args=[exe,"--remote-debugging-port=0","--remote-debugging-address=127.0.0.1",
                      "--user-data-dir="+str(profile),"--no-first-run","--no-default-browser-check",
                      "--disable-background-networking","--disable-component-update","--disable-sync",
                      "--password-store=basic","--use-mock-keychain","--enable-automation",
                      "--window-size=1500,1000"]
                if cfg["headless"]:args.append("--headless=new")
                if not cfg["sandbox"]:args.append("--no-sandbox")
                args.append("about:blank")
                process=subprocess.Popen(args,stdout=logfile,stderr=subprocess.STDOUT,env=browser_env(),start_new_session=True)
                active=profile/"DevToolsActivePort"
                for _ in range(150):
                    if process.poll() is not None:raise RuntimeError(f"{name} exited before CDP became available (check sandbox/platform prerequisites)")
                    if active.exists() and len(active.read_text().splitlines())>=2:break
                    await asyncio.sleep(.1)
                else:raise TimeoutError(f"CDP startup timeout: {name}")
                port=int(active.read_text().splitlines()[0]);endpoint=f"http://127.0.0.1:{port}"
            browser=await pw.chromium.connect_over_cdp(endpoint,timeout=15000)
            yield browser,"cdp"
        else:
            bt=getattr(pw,name)
            kwargs={"headless":cfg["headless"],"env":browser_env()}
            if cfg["executables"].get(name):kwargs["executable_path"]=cfg["executables"][name]
            browser=await bt.launch(**kwargs)
            yield browser,"playwright"
    finally:
        if browser:
            try:await browser.close()
            except Exception:pass
        if process:
            if process.poll() is None:
                process.terminate()
                try:await asyncio.to_thread(process.wait,5)
                except subprocess.TimeoutExpired:process.kill();await asyncio.to_thread(process.wait)
        if logfile:logfile.close()
        if profile:shutil.rmtree(profile,ignore_errors=True)


def context_options(cfg: dict, device: dict, name: str, scene: dict | None = None) -> dict:
    # Firefox does not implement Playwright's is_mobile. Its mobile cell is honestly viewport+touch.
    result={"viewport":{"width":device["width"],"height":device["height"]},
            "device_scale_factor":device["dpr"],"has_touch":device["touch"],
            "locale":cfg["locale"],"timezone_id":cfg["timezone"],
            "color_scheme":cfg["color_scheme"],"reduced_motion":"reduce",
            "service_workers":"block","accept_downloads":cfg.get("downloads",{}).get("enabled",False)}
    if name!="firefox":result["is_mobile"]=device["mobile"]
    from .sessions import state_for
    state=state_for(cfg,scene)
    if state is not None:result["storage_state"]=state
    return result
