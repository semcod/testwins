from __future__ import annotations
import copy
import re
from pathlib import Path
from urllib.parse import urljoin
from typing import Any
import yaml
from .util import origin

MATRICES = {
    "cdp": ["chrome", "edge", "brave"],
    "engines": ["chromium", "firefox", "webkit"],
    "chromium": ["chromium"],
}
DEVICES = {
    "desktop": {"width": 1440, "height": 900, "dpr": 1, "touch": False, "mobile": False},
    "tablet": {"width": 820, "height": 1180, "dpr": 2, "touch": True, "mobile": True},
    "mobile": {"width": 390, "height": 844, "dpr": 3, "touch": True, "mobile": True},
}
DEFAULT = {
    "schema": "testwins.config/v1", "project": "my-app", "base_url": "http://sut:8080",
    "matrix": "cdp", "devices": DEVICES, "routes": [{"id": "home", "path": "/"}],
    "ux": {"strategy": None, "habit": "standard", "budgets": {}},
    "journeys": [], "allowed_origins": [], "locale": "pl-PL", "timezone": "Europe/Warsaw",
    "color_scheme": "light", "headless": False, "sandbox": False,
    "executables": {}, "cdp_endpoints": {},
    "sessions": {}, "default_session": None,
    "downloads": {"enabled": False, "max_bytes": 10485760, "retain": False},
    "performance": {"enabled": False, "required": True, "budgets": {}},
    "capture": {"repeats": 2, "scroll_tiles": 3, "settle_ms": 180, "timeout_ms": 8000,
                "max_elements": 2500, "max_text_rects": 5000, "max_html_bytes": 2000000,
                "max_cell_seconds": 180, "ready_selector": "body",
                "mask_selectors": ["input", "textarea", "[contenteditable=true]", "[data-private]"],
                "freeze_animations": True, "before_steps": True},
    "rules": {"overlap_px": 2, "overlap_fraction": 0.12, "clip_px": 2,
              "target_px": 24, "alignment": [], "heuristic_alignment": True,
              "auth_form_standards": True},
    "axe": {"enabled": True, "required": True, "path": "/opt/testwins-assets/axe.min.js"},
    "baseline": {"directory": None, "threshold": 0.005, "color_delta": 24,
                 "fail_on_difference": False},
    "crawl": {"enabled": False, "allow_paths": [], "max_pages": 5},
    "suppressions": [], "overlays": [], "frames": [], "sticky_regions": [],
}


def closed(obj: Any, allowed: set[str], label: str) -> None:
    if not isinstance(obj, dict): raise ValueError(f"{label} must be an object")
    unknown = set(obj) - allowed
    if unknown: raise ValueError(f"unknown {label} fields: {sorted(unknown)}")


def bounded_int(v: Any, low: int, high: int, label: str) -> None:
    if type(v) is not int or not low <= v <= high:
        raise ValueError(f"{label} must be an integer in [{low}, {high}]")


def validate(cfg: dict) -> dict:
    closed(cfg, set(DEFAULT), "config")
    if cfg["schema"] != DEFAULT["schema"]: raise ValueError("unsupported config schema")
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", cfg["project"]):
        raise ValueError("project must be a stable lowercase identifier")
    base = origin(cfg["base_url"])
    if cfg["matrix"] not in MATRICES: raise ValueError("unknown browser matrix")
    if not cfg["devices"]: raise ValueError("empty device matrix")
    for name, d in cfg["devices"].items():
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", name): raise ValueError("invalid device id")
        closed(d, set(DEVICES["desktop"]), "device")
        for key in ("width", "height"): bounded_int(d[key], 200, 4000, key)
        bounded_int(d["dpr"], 1, 4, "dpr")
        for key in ("touch", "mobile"):
            if type(d[key]) is not bool: raise ValueError("device flags must be booleans")
    for key in ("capture", "rules", "axe", "baseline", "crawl", "downloads", "performance"):
        closed(cfg[key], set(DEFAULT[key]), key)
    c = cfg["capture"]
    for key, low, high in [("repeats",1,5),("scroll_tiles",1,20),("settle_ms",0,5000),
                           ("timeout_ms",100,60000),("max_elements",10,10000),
                           ("max_text_rects",10,20000),("max_html_bytes",1000,10000000),
                           ("max_cell_seconds",5,3600)]:
        bounded_int(c[key], low, high, key)
    if not isinstance(c["mask_selectors"], list) or not all(isinstance(s,str) for s in c["mask_selectors"]):
        raise ValueError("mask_selectors must be a list of CSS selectors")
    from .contracts import validate_extensions, validate_expectation
    validate_extensions(cfg)
    ids = set()
    for kind in ("routes", "journeys"):
        if not isinstance(cfg[kind], list): raise ValueError(f"{kind} must be a list")
        for item in cfg[kind]:
            closed(item, {"id", "path", "steps", "session", "setup_path", "frames"} if kind == "journeys" else {"id", "path", "session", "setup_path", "frames"}, kind)
            if item.get("session") is not None and item["session"] not in cfg["sessions"]:
                raise ValueError("Unknown scene session")
            if item.get("setup_path") is not None and origin(urljoin(cfg["base_url"], item["setup_path"])) != base:
                raise ValueError("setup_path leaves the target origin")
            name = item["id"]
            if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", name) or name in ids:
                raise ValueError("route/journey ids must be unique safe identifiers")
            ids.add(name)
            if origin(urljoin(cfg["base_url"], item["path"])) != base:
                raise ValueError("route leaves the target origin")
            steps = item.get("steps", [])
            if len(steps) > 100: raise ValueError("journey is too long")
            step_ids = set()
            for s in steps:
                closed(s, {"id","action","selector","value","key","expect","allow_mutation","ux","frame"}, "step")
                if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", s["id"]) or s["id"] in step_ids:
                    raise ValueError("invalid or duplicated step id")
                step_ids.add(s["id"])
                if s["action"] not in ("click","fill","press","hover","check","select","assert","download","goto","scroll"):
                    raise ValueError("unsupported action; arbitrary JavaScript and shell are forbidden")
                if s["action"] in ("click","fill","press","check","select","download","goto") and s.get("allow_mutation") is not True:
                    raise ValueError("mutating UI actions require allow_mutation: true in the operator-owned journey")
                if s["action"] not in ("assert", "goto") and not isinstance(s.get("selector"),str):
                    raise ValueError("action selector is required")
                if s["action"] in ("fill","select") and not isinstance(s.get("value"),str):
                    raise ValueError("fill/select value must be a string")
                if s["action"] == "press" and not isinstance(s.get("key"),str): raise ValueError("press key is required")
                if "expect" not in s: raise ValueError("every step requires an explicit UI expectation")
                if s["action"]=="goto":
                    if not isinstance(s.get("value"), str) or origin(urljoin(cfg["base_url"], s["value"])) != base:
                        raise ValueError("goto needs a same-origin value")
                validate_expectation(s["expect"])
                if (s["action"]=="download") != (s["expect"]["kind"]=="download"):
                    raise ValueError("download action and expectation must be paired")
                if s["action"]=="download" and not cfg["downloads"]["enabled"]:
                    raise ValueError("Explicit downloads.enabled: true is required")
    if not ids: raise ValueError("at least one route or journey is required")
    for a in cfg["allowed_origins"]: origin(a)
    for a in cfg["rules"]["alignment"]:
        closed(a, {"id","selector","edge","tolerance_px"}, "alignment contract")
        if a["edge"] not in ("left","right","top","bottom","center_x","center_y"):
            raise ValueError("unsupported alignment edge")
        if not 0 <= a["tolerance_px"] <= 100: raise ValueError("invalid alignment tolerance")
    bounded_int(cfg["crawl"]["max_pages"],1,50,"max_pages")
    if cfg["crawl"]["enabled"] and not cfg["crawl"]["allow_paths"]:
        raise ValueError("crawling requires explicit path allowlists")
    for container, key in [(cfg,"headless"),(cfg,"sandbox"),(cfg["capture"],"freeze_animations"),
                           (cfg["axe"],"enabled"),(cfg["axe"],"required"),(cfg["crawl"],"enabled"),
                           (cfg["rules"],"heuristic_alignment"),(cfg["baseline"],"fail_on_difference")]:
        if type(container[key]) is not bool:raise ValueError(key+" must be boolean")
    for key in ("overlap_px","clip_px","target_px"):
        v=cfg["rules"][key]
        if type(v) not in (int,float) or not 0<v<=100:raise ValueError("invalid rule threshold "+key)
    for container,key in [(cfg["rules"],"overlap_fraction"),(cfg["baseline"],"threshold")]:
        v=container[key]
        if type(v) not in (int,float) or not 0<=v<=1:raise ValueError("invalid proportion "+key)
    bounded_int(cfg["baseline"]["color_delta"],0,255,"color_delta")
    if cfg["color_scheme"] not in ("light","dark","no-preference"):raise ValueError("invalid color scheme")
    for which in ("executables","cdp_endpoints"):
        if set(cfg[which])-set(sum(MATRICES.values(),[])):raise ValueError("unknown browser override")
        if not all(isinstance(x,str) and x for x in cfg[which].values()):raise ValueError("invalid browser override")
    for s in cfg["suppressions"]:
        closed(s,{"rule","selector","route","reason","owner","expires"},"suppression")
        if not s.get("reason") or not s.get("owner") or not s.get("expires"):
            raise ValueError("suppressions need reason, owner and expiry")
        from datetime import date
        date.fromisoformat(str(s["expires"]))
    from .overlays import validate_overlays
    validate_overlays(cfg)
    from .frames import validate_frames
    validate_frames(cfg)
    from .sticky import validate_sticky_regions
    validate_sticky_regions(cfg)
    from .ux import validate_ux
    validate_ux(cfg)
    return cfg


def load(path: Path | None = None, **overrides: Any) -> dict:
    cfg = copy.deepcopy(DEFAULT)
    raw = yaml.safe_load(path.read_text("utf-8")) if path else {}
    raw = raw or {}
    closed(raw, set(DEFAULT), "config")
    for key, value in raw.items():
        if isinstance(cfg.get(key), dict) and key != "devices":
            closed(value, set(cfg[key]) if key not in ("executables","cdp_endpoints","sessions") else set(value), key)
            cfg[key].update(value)
        else: cfg[key] = value
    for key, value in overrides.items():
        if value is not None: cfg[key] = value
    if path:
        for session in cfg["sessions"].values():
            local=Path(session["storage_state"]).expanduser()
            if not local.is_absolute(): local=path.resolve().parent/local
            session["storage_state"]=str(local.absolute())
    return validate(cfg)
