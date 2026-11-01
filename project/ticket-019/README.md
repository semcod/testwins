# ticket-019 — Exclude errors/README.md in standards checker, guard optional cv2/numpy/typer test deps, and align version SSOT

## Goal
Exclude `errors/README.md` when collecting error codes in `tools/standards.py` (`B09`), guard optional `cv2`/`numpy`/`typer` imports in `tests/test_extensions.py` and `tests/live/test_live_io.py` and exclude `.worktrees`/`.governance` in `tools/release.py` (`B02`), and align version `0.4.1` SSOT across `README.md`, `verification/summary.json`, and `tests/test_release_contracts.py` (`B03`).

## Acceptance Criteria
1. `tools/standards.py` excludes `README.md` from `errors/*.md` error code discovery.
2. `tests/test_extensions.py` and `tests/live/test_live_io.py` skip cleanly via `pytest.importorskip` when `cv2`, `numpy`, or `typer` is not installed.
3. `VERSION`, `pyproject.toml`, `testwins.__version__`, `README.md`, and `verification/summary.json` all agree on `0.4.1`.
