# ticket-018 — Opt-in autoupdate, config/browser display env fixes, live catalog/IPv6 server parity, and suite/staging hardening

## Goal
Disable implicit background PyPI polling and `pip install --upgrade` self-mutation by default (`B01`), validate `auth_form_standards` boolean and preserve `XAUTHORITY` / `WAYLAND_DISPLAY` in `browser_env` (`B04`), synchronize `TW-STICKY-CONTRACT` + automatic rules in `live/catalog.json` and IPv6/`--host` handling in `live-serve` (`B06`), and wire `suite --project` plus `.worktrees` exclusion in `staging.py` (`B08`).

## Acceptance Criteria
1. `check_for_updates` is opt-in (`TESTWINS_AUTOUPDATE=1`) and never executes `pip install --upgrade`.
2. `config.validate` rejects non-boolean `rules.auth_form_standards` and `capture.before_steps`, resolves `TESTWINS_AXE_PATH`, and `browser_env()` preserves `XAUTHORITY` and `WAYLAND_DISPLAY`.
3. `BASE_RULES <= set(BY_RULE)`, `live/server.py` handles IPv6 `Host: [::1]:port`, and `live-serve` accepts `--host` and `--allow-expose`.
4. `testwins suite --project` forwards `project` to `run_suite`, and `testwins.staging.stage` excludes `.worktrees`, `.koru`, `.governance`, and `.ruff_cache`.
