from __future__ import annotations
import json
import shutil
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw
from .util import atomic_json, digest, confined
from .model import Finding


def baseline_key(meta: dict) -> str:
    return digest({k:meta[k] for k in ("project","browser","device","stage","viewport_profile","locale","timezone","color_scheme")})


def compare(current: Path, reference: Path, diff_path: Path, color_delta: int=24) -> dict:
    with Image.open(current) as a0, Image.open(reference) as b0:
        a,b=a0.convert("RGB"),b0.convert("RGB")
        if a.size!=b.size:return {"ratio":1.0,"dimensions_changed":True,"current":list(a.size),"baseline":list(b.size)}
        diff=ImageChops.difference(a,b)
        channels=diff.split();maximum=ImageChops.lighter(ImageChops.lighter(channels[0],channels[1]),channels[2])
        mask=maximum.point(lambda p:255 if p>color_delta else 0)
        hist=mask.histogram();changed=hist[255];total=a.width*a.height
        overlay=b.copy();overlay.paste((255,32,100),(0,0,a.width,a.height),mask)
        diff_path.parent.mkdir(parents=True,exist_ok=True);overlay.save(diff_path)
        return {"ratio":changed/total,"changed_pixels":changed,"pixels":total,"dimensions_changed":False}


def assess(image: Path, meta: dict, cfg: dict, dest: Path) -> tuple[list[dict],str]:
    directory=cfg["baseline"]["directory"]
    if not directory:return [],"disabled"
    root=Path(directory);key=baseline_key(meta);ref=root/(key+".png");md=root/(key+".json")
    if not ref.exists() or not md.exists():return [],"missing"
    previous=json.loads(md.read_text())
    # Engine version changes invalidate a pixel baseline, rather than create hundreds of bogus bugs.
    if previous.get("browser_version")!=meta.get("browser_version"):return [],"incompatible_browser_version"
    if previous.get("render_environment")!=meta.get("render_environment"):return [],"incompatible_render_environment"
    res=compare(image,ref,dest,cfg["baseline"]["color_delta"])
    if res["ratio"]<=cfg["baseline"]["threshold"]:return [],"matched"
    candidate=not cfg["baseline"]["fail_on_difference"]
    f=Finding("TW-VISUAL-REGRESSION","Zmiana względem zatwierdzonego obrazu",
              f"Różnica przekracza próg: {res['ratio']:.3%}. Zmiana obrazu sama nie dowodzi błędu.",
              ["viewport"],[],"normal",.70 if candidate else .98,candidate,res)
    return [f.to_dict()],"different"


def approve(run: Path, destination: Path, *, authorized: bool) -> int:
    if not authorized:raise ValueError("baseline approval requires --approve")
    report=json.loads((run/"report.json").read_text())
    if report["coverage"]["state"]!="complete":raise ValueError("cannot approve an incomplete matrix")
    destination.mkdir(parents=True,exist_ok=True);done=set()
    for s in report["snapshots"]:
        if not s["stable"]:continue
        key=baseline_key(s["meta"])
        if key in done:continue
        done.add(key)
        shutil.copy2(confined(run,s["image"]),destination/(key+".png"))
        atomic_json(destination/(key+".json"),s["meta"])
    return len(done)
