"""First-class CLI subcommand for 2D ANSI/VT100 terminal surface audits."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .integrations.terminal import PyteTerminalSurface, TerminalSession
from .util import atomic_json

MAX_INPUT_BYTES = 2 * 1024 * 1024


def register_tui(sub: Any) -> None:
    p = sub.add_parser(
        "tui",
        help="Audit 2D ANSI/VT100 terminal surface geometry, truecolor palette, and text contracts",
    )
    p.add_argument("--input", type=Path, help="Path to captured ANSI/VT100 frame file")
    p.add_argument("--exec", dest="exec_bin", help="Executable to run inside an isolated PTY")
    p.add_argument(
        "cmd_argv",
        nargs="*",
        help="Optional command/arguments to execute inside an isolated PTY (pass after --)",
    )
    p.add_argument("--cwd", type=Path, default=Path("."), help="Working directory for PTY command")
    p.add_argument("--cols", type=int, default=120, help="Terminal width in columns (8..500)")
    p.add_argument("--rows", type=int, default=36, help="Terminal height in rows (4..200)")
    p.add_argument("--timeout", type=float, default=5.0, help="PTY read timeout in seconds (0.1..60)")
    p.add_argument(
        "--expect-text",
        dest="expect_text",
        action="append",
        default=[],
        help="Repeatable substring assertion that must appear on the rendered 2D surface",
    )
    p.add_argument(
        "--palette",
        action="append",
        default=[],
        help="Repeatable hex color token (e.g. #38bdf8) allowed on the surface",
    )
    p.add_argument("--output", type=Path, help="Optional JSON report output file")


def run_tui_audit(
    *,
    input_file: Path | None = None,
    exec_bin: str | None = None,
    exec_args: list[str] | None = None,
    cwd: Path = Path("."),
    cols: int = 120,
    rows: int = 36,
    timeout: float = 5.0,
    expect_text: list[str] | None = None,
    palette: list[str] | None = None,
    output_file: Path | None = None,
) -> dict[str, Any]:
    cmd: list[str] = []
    if exec_bin:
        cmd.append(str(exec_bin))
    if exec_args:
        cmd.extend(str(x) for x in exec_args)
    if bool(input_file) == bool(cmd):
        raise ValueError("Specify either --input <file> or a PTY command (--exec / -- <cmd...>)")
    if not (8 <= int(cols) <= 500 and 4 <= int(rows) <= 200):
        raise ValueError("tui dimensions must be cols 8..500 and rows 4..200")
    if not (0.1 <= float(timeout) <= 60.0):
        raise ValueError("timeout must be 0.1..60.0 seconds")

    if input_file is not None:
        if input_file.is_symlink() or not input_file.is_file():
            raise ValueError(f"Invalid --input file: {input_file}")
        raw_bytes = input_file.read_bytes()
        if len(raw_bytes) > MAX_INPUT_BYTES:
            raise ValueError("--input exceeds 2 MiB budget")
        surface = PyteTerminalSurface(cols=int(cols), rows=int(rows))
        surface.feed(raw_bytes.decode("utf-8", errors="replace"))
    else:
        if any(not part or "\x00" in part for part in cmd):
            raise ValueError("Invalid PTY command arguments")
        with TerminalSession(
            cmd[0],
            cmd[1:],
            cwd=cwd.resolve(),
            cols=int(cols),
            rows=int(rows),
        ) as session:
            if expect_text:
                for token in expect_text:
                    if token:
                        session.wait_for_text(str(token), timeout_s=float(timeout))
            else:
                session.drain(timeout_s=min(float(timeout), 0.5))
            surface = session.surface

    palette_set = {str(c).strip().lower() for c in (palette or []) if str(c).strip()} or None
    findings = surface.audit_tui_parity(expected_hex_tokens=palette_set)
    missing_text: list[str] = []
    matched_text: dict[str, list[dict[str, Any]]] = {}
    for token in expect_text or []:
        needle = str(token)
        if not needle:
            continue
        hits = surface.find_text(needle)
        matched_text[needle] = hits
        if not hits:
            missing_text.append(needle)
            findings.append(
                {
                    "rule": "TW-TUI-TEXT-MISSING",
                    "severity": "error",
                    "message": f"Expected text {needle!r} not found on rendered terminal surface",
                }
            )

    passed = len(findings) == 0
    report: dict[str, Any] = {
        "schema": "testwins.tui-report/v1",
        "status": "passed" if passed else "failed",
        "exit_code": 0 if passed else 1,
        "cols": surface.cols,
        "rows": surface.rows,
        "boxes": surface.detect_boxes(),
        "findings": findings,
        "missing_text": missing_text,
        "matched_text": matched_text,
        "lines": surface.lines(),
    }
    if output_file is not None:
        atomic_json(output_file, report)
    return report


def dispatch_tui(args: argparse.Namespace) -> int:
    report = run_tui_audit(
        input_file=args.input,
        exec_bin=args.exec_bin,
        exec_args=list(args.cmd_argv or []),
        cwd=args.cwd,
        cols=args.cols,
        rows=args.rows,
        timeout=args.timeout,
        expect_text=list(args.expect_text or []),
        palette=list(args.palette or []),
        output_file=args.output,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(report["exit_code"])
