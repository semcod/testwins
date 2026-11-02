# ticket-021 — First-class `testwins tui` CLI subcommand wrapping `PyteTerminalSurface`

## Goal
Expose `PyteTerminalSurface` and `TerminalSession` via a first-class `testwins tui` CLI subcommand (`PLF-2565`) so operators and CI pipelines can audit ANSI/VT100 terminal frames (`--input`) or live PTY commands (`--exec` / `--arg`) for 2D box geometry, truecolor palette drift (`--palette`), and required text assertions (`--expect-text`), and declare `pyte>=0.8.2,<1` in `[project.optional-dependencies].terminal`.

## Acceptance Criteria
1. `testwins tui` accepts `--input <file>` or `--exec <binary> [--arg ...]`, `--cols`, `--rows`, `--expect-text`, `--palette`, and `--output`, emitting `testwins.tui-report/v1` JSON and returning exit code `0` on pass or `1` on parity/assertion failure.
2. `pyproject.toml` includes `pyte>=0.8.2,<1` under `[project.optional-dependencies].terminal`.
3. Deterministic unit and CLI tests in `tests/test_tui_cli.py` pass without `pytest.skip`.
