"""Autonomous non-blocking background update checker and auto-upgrader for CLI tools.

Checks PyPI for package updates at most once every TTL interval (default: 24h).
Spawns a detached background process with zero network delay on the CLI invocation.
If an update is available:
- If AUTO_UPGRADE=1 or <PKG>_AUTO_UPGRADE=1: spawns a background pip install --upgrade.
- Otherwise, reports cleanly on stderr.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from importlib import metadata
from pathlib import Path


def _get_cache_dir(pkg_name: str) -> Path:
    """Return platform cache directory for package update tracking."""
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        base = Path(xdg_cache)
    else:
        base = Path.home() / ".cache"
    pkg_cache = base / pkg_name
    pkg_cache.mkdir(parents=True, exist_ok=True)
    return pkg_cache


def _is_newer(latest: str, current: str) -> bool:
    """Check if latest is strictly newer than current, with zero hard dependency."""
    try:
        from packaging import version
        return version.parse(latest) > version.parse(current)
    except Exception:
        pass

    def parse_simple(v: str) -> tuple:
        nums = []
        for part in v.split("."):
            digits = ""
            for ch in part:
                if ch.isdigit():
                    digits += ch
                else:
                    break
            nums.append(int(digits) if digits else 0)
        return tuple(nums)

    return parse_simple(latest) > parse_simple(current)


def _spawn_detached_check(pkg_name: str, current_version: str, cache_file: Path) -> None:
    """Launch completely detached background worker process."""
    worker_code = f"""
import json, sys, time
from urllib import request
from pathlib import Path

pkg_name = {pkg_name!r}
current_version = {current_version!r}
cache_file = Path({str(cache_file)!r})

latest = None
try:
    url = f"https://pypi.org/pypi/{{pkg_name}}/json"
    req = request.Request(url, headers={{"User-Agent": f"{{pkg_name}}-autoupdate"}})
    with request.urlopen(req, timeout=3.0) as resp:
        if resp.status == 200:
            data = json.loads(resp.read().decode("utf-8"))
            latest = data.get("info", {{}}).get("version")
except Exception:
    pass

cache_data = {{
    "last_check": time.time(),
    "current_version": current_version,
    "latest_version": latest or current_version,
}}
try:
    cache_file.write_text(json.dumps(cache_data), encoding="utf-8")
except Exception:
    pass
"""
    try:
        subprocess.Popen(
            [sys.executable, "-c", worker_code],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


def _spawn_background_upgrade(pkg_name: str) -> None:
    """Spawn background pip install --upgrade if auto-upgrade is enabled."""
    try:
        subprocess.Popen(
            [sys.executable, "-m", "pip", "install", "--upgrade", "--quiet", "--disable-pip-version-check", pkg_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


def check_for_updates(
    pkg_name: str,
    ttl_seconds: int = 86400,  # 24 hours
    *,
    enabled: bool = False,
) -> None:
    """Opt-in non-blocking check for package updates.

    Disabled by default so offline/CI/sandboxed runs never initiate implicit PyPI
    requests or mutate the active Python environment via background `pip install`.
    Set `TESTWINS_AUTOUPDATE=1` (or pass `enabled=True`) to opt in to read-only
    update notifications on stderr.
    """
    safe_pkg = pkg_name.upper().replace("-", "_")
    opt_in = enabled or os.environ.get("TESTWINS_AUTOUPDATE") == "1" or os.environ.get(f"{safe_pkg}_AUTOUPDATE") == "1"
    if not opt_in or os.environ.get("CI") or os.environ.get("NO_AUTOUPDATE"):
        return

    try:
        current_version = metadata.version(pkg_name)
    except Exception:
        return

    cache_dir = _get_cache_dir(pkg_name)
    cache_file = cache_dir / "update_check.json"

    should_query = True
    cached_latest = None

    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            last_check = cached.get("last_check", 0)
            cached_latest = cached.get("latest_version")
            if time.time() - last_check < ttl_seconds:
                should_query = False
        except Exception:
            pass

    if cached_latest and cached_latest != current_version:
        try:
            if _is_newer(cached_latest, current_version):
                sys.stderr.write(
                    "\n💡 [" + pkg_name + "] Nowa wersja dostępna: "
                    + current_version + " → " + cached_latest + "\n"
                    + "   Aby zaktualizować, uruchom jawnie: pip install --upgrade " + pkg_name + "\n\n"
                )
                sys.stderr.flush()
        except Exception:
            pass

    if should_query:
        _spawn_detached_check(pkg_name, current_version, cache_file)
