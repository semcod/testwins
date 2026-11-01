# ticket-020 — Pyte 2D terminal surface inspector and raw/resize PTY session driver

## Goal
Extend `testwins/integrations/terminal.py` and `testwins/tasks.py` (`B10`) with `PyteTerminalSurface` (2D cell-grid, ANSI/24-bit RGB foreground/background attribute inspection, Unicode box-drawing geometry detection, and TUI parity detectors `TW-TUI-BOX-BROKEN` / `TW-TUI-COLOR-DRIFT` / `TW-TUI-EMPTY-SURFACE`) and `TerminalSession` (`send_raw`, dynamic `resize` with `TIOCSWINSZ` + `SIGWINCH`, and `TERM=xterm-256color` / `COLORTERM=truecolor` preservation).

## Acceptance Criteria
1. `PyteTerminalSurface` decodes VT100/ANSI/truecolor sequences into a 2D cell grid, extracts box-drawing frames, and detects broken frames and off-palette 24-bit colors.
2. `TerminalSession` supports raw keystrokes (`send_raw`), live PTY `resize(cols, rows)` (`TIOCSWINSZ` + `SIGWINCH`), and truecolor env preservation without leaking host secrets.
3. Existing Pexpect `execute()` tests remain 100% backward compatible while supporting `send_raw`, `resize`, `cols`, `rows`, and `color`.
