from __future__ import annotations
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode


def canonical(value: Any, *, integers_only: bool = False) -> bytes:
    def check(v: Any) -> None:
        if isinstance(v, float):
            raise ValueError("floating point numbers are excluded from the log contract")
        if isinstance(v, dict):
            for child in v.values(): check(child)
        elif isinstance(v, (list, tuple)):
            for child in v: check(child)
    if integers_only: check(value)
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""): h.update(chunk)
    return h.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            f.write("\n"); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def confined(root: Path, relative: str) -> Path:
    if Path(relative).is_absolute() or ".." in Path(relative).parts: raise ValueError("absolute/traversal artifact path is not allowed")
    p = (root / relative).resolve()
    if not p.is_relative_to(root.resolve()): raise ValueError("artifact path escapes its root")
    return p


def slug(text: str) -> str:
    normalized=re.sub(r"[^a-zA-Z0-9_.-]", "-", text) or "item"
    return normalized if len(normalized)<=100 else normalized[:79]+"-"+digest(text)[:20]


def redact_url(url: str) -> str:
    u = urlsplit(url)
    sensitive = re.compile(r"token|secret|password|key|auth|session|code|email", re.I)
    host = u.hostname or ""
    if ":" in host: host = "[" + host + "]"
    if u.port: host += f":{u.port}"
    query = urlencode([(k, "REDACTED" if sensitive.search(k) else v) for k,v in parse_qsl(u.query)])
    fragment="REDACTED" if sensitive.search(u.fragment) and "=" in u.fragment else u.fragment
    return urlunsplit((u.scheme, host, u.path, query, fragment))


def origin(url: str) -> str:
    u = urlsplit(url)
    if u.scheme not in ("http", "https") or not u.hostname or u.username or u.password:
        raise ValueError("an HTTP(S) URL without embedded credentials is required")
    port = u.port or (443 if u.scheme == "https" else 80)
    return f"{u.scheme}://{u.hostname.lower()}:{port}"
