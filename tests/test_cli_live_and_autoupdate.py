"""Regression tests for ticket-018 CLI, autoupdate, config, browser env, live server, suite, and staging fixes."""

from __future__ import annotations

import subprocess
from pathlib import Path
from urllib.request import Request, urlopen

import pytest
import yaml

from testwins import autoupdate
from testwins.browser import browser_env
from testwins.cli import parser
from testwins.config import load
from testwins.live.server import Server
from testwins.live.store import Store
from testwins.staging import stage
from testwins.suite import run_suite


def test_autoupdate_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    spawned: list[object] = []
    monkeypatch.delenv("TESTWINS_AUTOUPDATE", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("NO_AUTOUPDATE", raising=False)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: spawned.append((a, kw)))
    autoupdate.check_for_updates("testwins")
    assert spawned == []


def test_config_rejects_non_boolean_auth_form_standards_and_resolves_env_axe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump({"rules": {"auth_form_standards": "yes"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="auth_form_standards must be boolean"):
        load(bad)

    fake_axe = tmp_path / "axe.min.js"
    fake_axe.write_text("window.axe={};", encoding="utf-8")
    monkeypatch.setenv("TESTWINS_AXE_PATH", str(fake_axe))
    cfg = load()
    assert cfg["axe"]["path"] == str(fake_axe)


def test_browser_env_preserves_xauthority_and_wayland(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XAUTHORITY", "/tmp/.Xauthority-test")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-leak")
    env = browser_env()
    assert env["XAUTHORITY"] == "/tmp/.Xauthority-test"
    assert env["WAYLAND_DISPLAY"] == "wayland-0"
    assert "OPENAI_API_KEY" not in env


def test_live_serve_parser_and_ipv6_host_header(tmp_path: Path) -> None:
    args = parser().parse_args(["live-serve", str(tmp_path), "--host", "127.0.0.1", "--port", "0"])
    assert args.host == "127.0.0.1"
    assert args.allow_expose is False

    store = Store(tmp_path / "live.sqlite")
    srv = Server(store, host="127.0.0.1", port=0)
    srv.start()
    try:
        req = Request(f"http://127.0.0.1:{srv.port}/api/status", headers={"Host": f"[::1]:{srv.port}"})
        with urlopen(req, timeout=3) as resp:
            assert resp.status == 200
    finally:
        srv.close()
        store.close()


def test_staging_excludes_nested_worktrees_and_suite_validates_step_id(tmp_path: Path) -> None:
    app = tmp_path / "app"
    app.mkdir()
    (app / "index.html").write_text("<h1>Heyasa</h1>", encoding="utf-8")
    wt = app / ".worktrees" / "ticket-001--demo"
    wt.mkdir(parents=True)
    (wt / "dangling").symlink_to("/etc/passwd")
    staged = stage(app, tmp_path / "staged")
    assert staged["files"] == 1

    bad_suite = tmp_path / "bad.suite.yaml"
    bad_suite.write_text(
        yaml.safe_dump({"schema": "testwins.suite/v1", "id": "demo", "steps": [{"kind": "web", "config": "x.yaml"}]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Invalid suite step"):
        run_suite(bad_suite, tmp_path / "out")
