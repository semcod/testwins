"""Bounded POSIX terminal tests and 2D VT100/ANSI TUI surface inspector (Pexpect + Pyte)."""
from __future__ import annotations

import fcntl
import os
import pty
import re
import select
import signal
import struct
import subprocess
import termios
import time
from pathlib import Path
from typing import Any

from ..util import atomic_json, confined

TOP_LEFT_CORNERS = {"┌": ("┐", "└", "┘"), "╭": ("╮", "╰", "╯"), "┏": ("┓", "┗", "┛"), "╔": ("╗", "╚", "╝")}
RIGHT_BORDERS = {"│", "┃", "║", "┐", "┘", "╮", "╯", "┓", "┛", "╗", "╝", "┤", "┫", "╣"}


def _normalize_color(value: Any) -> str:
    if not value or value == "default":
        return "default"
    text = str(value).strip().lower()
    if re.fullmatch(r"[0-9a-f]{6}", text):
        return f"#{text}"
    return text


class OutputBudget:
    """Read sink counts even unmatched output; raw terminal data is never retained."""

    def __init__(self, limit: int):
        self.limit = limit
        self.used = 0

    def write(self, data: str | bytes) -> None:
        self.used += len(data.encode("utf-8")) if isinstance(data, str) else len(data)
        if self.used > self.limit:
            raise ValueError("Terminal output budget exceeded")

    def flush(self) -> None:
        pass


class PyteTerminalSurface:
    """2D cell-grid, ANSI/truecolor attribute, and box-drawing parity inspector using pyte."""

    def __init__(self, cols: int = 120, rows: int = 36) -> None:
        if cols < 20 or cols > 500 or rows < 5 or rows > 200:
            raise ValueError("Terminal surface dimensions out of bounds")
        try:
            import pyte
        except ImportError as exc:
            raise RuntimeError(
                "pyte is required for 2D terminal surface inspection; install pyte or testwins[terminal]"
            ) from exc
        self._pyte = pyte
        self.cols = cols
        self.rows = rows
        self.screen = pyte.Screen(cols, rows)
        self.stream = pyte.Stream(self.screen)

    def feed(self, data: str | bytes) -> None:
        text = data.decode("utf-8", errors="replace") if isinstance(data, bytes) else data
        self.stream.feed(text)

    def resize(self, cols: int, rows: int) -> None:
        if cols < 20 or cols > 500 or rows < 5 or rows > 200:
            raise ValueError("Terminal surface dimensions out of bounds")
        self.cols = cols
        self.rows = rows
        self.screen.resize(rows, cols)

    def lines(self) -> list[str]:
        return [line.rstrip() for line in self.screen.display]

    def raw_lines(self) -> list[str]:
        return list(self.screen.display)

    def text(self) -> str:
        return "\n".join(self.lines())

    def cell(self, row: int, col: int) -> dict[str, Any]:
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            raise IndexError(f"Cell ({row}, {col}) outside ({self.rows}, {self.cols})")
        default_char = self.screen.default_char
        ch = self.screen.buffer[row].get(col, default_char)
        return {
            "row": row,
            "col": col,
            "char": ch.data or " ",
            "fg": _normalize_color(ch.fg),
            "bg": _normalize_color(ch.bg),
            "bold": bool(ch.bold),
            "italics": bool(ch.italics),
            "underscore": bool(ch.underscore),
            "reverse": bool(ch.reverse),
        }

    def find_text(self, needle: str) -> list[dict[str, Any]]:
        if not needle:
            raise ValueError("Search text must be non-empty")
        matches: list[dict[str, Any]] = []
        for r, line in enumerate(self.screen.display):
            start = 0
            while True:
                idx = line.find(needle, start)
                if idx == -1:
                    break
                cell_info = self.cell(r, idx)
                matches.append(
                    {
                        "row": r,
                        "col": idx,
                        "text": needle,
                        "fg": cell_info["fg"],
                        "bg": cell_info["bg"],
                        "bold": cell_info["bold"],
                    }
                )
                start = idx + 1
        return matches

    def detect_boxes(self) -> list[dict[str, Any]]:
        """Detect 2D Unicode box-drawing pane and modal rectangles."""
        grid = self.screen.display
        boxes: list[dict[str, Any]] = []
        for r0 in range(self.rows - 1):
            row_str = grid[r0]
            for c0 in range(self.cols - 1):
                ch = row_str[c0]
                if ch not in TOP_LEFT_CORNERS:
                    continue
                tr_ch, bl_ch, br_ch = TOP_LEFT_CORNERS[ch]
                c1 = row_str.find(tr_ch, c0 + 1)
                if c1 == -1:
                    continue
                r1 = -1
                for cand_r in range(r0 + 1, self.rows):
                    if grid[cand_r][c0] == bl_ch and grid[cand_r][c1] == br_ch:
                        r1 = cand_r
                        break
                if r1 != -1:
                    corner_cell = self.cell(r0, c0)
                    boxes.append(
                        {
                            "top": r0,
                            "left": c0,
                            "bottom": r1,
                            "right": c1,
                            "width": c1 - c0 + 1,
                            "height": r1 - r0 + 1,
                            "style": ch,
                            "border_fg": corner_cell["fg"],
                            "border_bg": corner_cell["bg"],
                        }
                    )
        return boxes

    def audit_tui_parity(
        self,
        *,
        expected_hex_tokens: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Run deterministic 2D TUI visual parity detectors analogous to DOM detectors."""
        findings: list[dict[str, Any]] = []
        grid = self.screen.display
        if all(not line.strip() for line in grid):
            findings.append(
                {
                    "rule": "TW-TUI-EMPTY-SURFACE",
                    "severity": "high",
                    "message": "Terminal surface has zero rendered characters.",
                    "coords": [],
                }
            )
            return findings

        # Check unclosed top-left box corners (clipped or broken pane/modal border)
        matched_corners = {(b["top"], b["left"]) for b in self.detect_boxes()}
        for r in range(self.rows):
            for c in range(self.cols):
                if grid[r][c] in TOP_LEFT_CORNERS and (r, c) not in matched_corners:
                    # Ignore corners inside text strings unless adjacent to horizontal rule
                    horiz = c + 1 < self.cols and grid[r][c + 1] in {"─", "━", "═"}
                    vert = r + 1 < self.rows and grid[r + 1][c] in {"│", "┃", "║"}
                    if horiz and vert:
                        findings.append(
                            {
                                "rule": "TW-TUI-BOX-BROKEN",
                                "severity": "high",
                                "message": f"Unclosed box-drawing frame starting at ({r}, {c}).",
                                "coords": [{"row": r, "col": c}],
                            }
                        )

        # Check brand hex color token conformance when expected_hex_tokens is provided
        if expected_hex_tokens:
            allowed = {t.lower() for t in expected_hex_tokens}
            drifted: dict[str, dict[str, int]] = {}
            for r in range(self.rows):
                for c in range(self.cols):
                    info = self.cell(r, c)
                    for key in ("fg", "bg"):
                        val = info[key]
                        if val.startswith("#") and val not in allowed and val not in drifted:
                            drifted[val] = {"row": r, "col": c}
            for color_val, pos in sorted(drifted.items()):
                findings.append(
                    {
                        "rule": "TW-TUI-COLOR-DRIFT",
                        "severity": "normal",
                        "message": f"Rendered 24-bit color {color_val} is outside declared brand tokens.",
                        "coords": [pos],
                        "color": color_val,
                    }
                )
        return findings


def _terminal_env(*, color: bool = True) -> dict[str, str]:
    allowed = {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT", "WINDIR"}
    env = {k: v for k, v in os.environ.items() if k in allowed}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    if color:
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"
    else:
        env["TERM"] = "dumb"
        env["NO_COLOR"] = "1"
    return env


def _set_winsize(fd: int, rows: int, cols: int) -> None:
    packed = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, packed)


class TerminalSession:
    """Interactive POSIX PTY session supporting raw keystrokes, dynamic resize, and Pyte 2D surface sync."""

    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        *,
        cwd: Path | None = None,
        cols: int = 120,
        rows: int = 36,
        color: bool = True,
        max_output_bytes: int = 262144,
        use_surface: bool = True,
    ) -> None:
        if not isinstance(command, str) or not command:
            raise ValueError("command must be a non-empty string")
        self.cols = cols
        self.rows = rows
        self.budget = OutputBudget(max_output_bytes)
        self.surface = PyteTerminalSurface(cols=cols, rows=rows) if use_surface else None
        master_fd, slave_fd = pty.openpty()
        _set_winsize(slave_fd, rows, cols)
        env = _terminal_env(color=color)
        try:
            self._proc = subprocess.Popen(
                [command, *(args or [])],
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                cwd=str(cwd) if cwd else None,
                env=env,
                start_new_session=True,
                close_fds=True,
            )
        except Exception:
            os.close(master_fd)
            os.close(slave_fd)
            raise
        os.close(slave_fd)
        self._master_fd: int | None = master_fd

    def send(self, line: str) -> None:
        self.send_raw(line + "\n")

    def send_raw(self, data: str | bytes) -> None:
        if self._master_fd is None:
            raise RuntimeError("TerminalSession is closed")
        raw = data.encode("utf-8") if isinstance(data, str) else data
        os.write(self._master_fd, raw)

    def resize(self, cols: int, rows: int) -> None:
        if self._master_fd is None:
            raise RuntimeError("TerminalSession is closed")
        self.cols = cols
        self.rows = rows
        _set_winsize(self._master_fd, rows, cols)
        if self.surface is not None:
            self.surface.resize(cols, rows)
        if self._proc.poll() is None:
            try:
                os.killpg(self._proc.pid, signal.SIGWINCH)
            except ProcessLookupError:
                pass

    def drain(self, timeout_s: float = 0.2) -> str:
        if self._master_fd is None:
            return ""
        chunks: list[bytes] = []
        deadline = time.monotonic() + max(0.0, timeout_s)
        while True:
            remaining = max(0.0, deadline - time.monotonic())
            ready, _, _ = select.select([self._master_fd], [], [], remaining)
            if not ready:
                break
            try:
                chunk = os.read(self._master_fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            self.budget.write(chunk)
            chunks.append(chunk)
            if time.monotonic() >= deadline:
                break
        decoded = b"".join(chunks).decode("utf-8", errors="replace")
        if decoded and self.surface is not None:
            self.surface.feed(decoded)
        return decoded

    def wait_for_text(self, needle: str, timeout_s: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout_s
        accumulated = ""
        while time.monotonic() < deadline:
            accumulated += self.drain(timeout_s=min(0.1, max(0.01, deadline - time.monotonic())))
            if self.surface is not None and self.surface.find_text(needle):
                return True
            if needle in accumulated:
                return True
            if self._proc.poll() is not None:
                accumulated += self.drain(timeout_s=0.05)
                if self.surface is not None and self.surface.find_text(needle):
                    return True
                return needle in accumulated
        return False

    def close(self) -> int | None:
        if self._master_fd is not None:
            try:
                os.close(self._master_fd)
            except OSError:
                pass
            self._master_fd = None
        if self._proc.poll() is None:
            try:
                os.killpg(self._proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(self._proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                self._proc.wait(timeout=2)
        return self._proc.returncode

    def __enter__(self) -> TerminalSession:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


def execute(task: dict, project: Path, output: Path) -> dict:
    import pexpect

    command = task.get("command")
    args = task.get("args", [])
    if (
        not isinstance(command, str)
        or not command
        or not isinstance(args, list)
        or not all(isinstance(x, str) for x in args)
    ):
        raise ValueError("Terminal task needs command and string args (no implicit shell)")
    limit = task.get("max_output_bytes", 262144)
    if type(limit) is not int or not 1024 <= limit <= 2_000_000:
        raise ValueError("Invalid terminal output limit")
    cols = task.get("cols", 120)
    rows = task.get("rows", 36)
    color = task.get("color", True)
    if type(cols) is not int or not 20 <= cols <= 500 or type(rows) is not int or not 5 <= rows <= 200:
        raise ValueError("Invalid terminal dimensions")
    if type(color) is not bool:
        raise ValueError("Invalid terminal color setting")

    steps = task["steps"]
    allowed_actions = {"send", "send_raw", "resize", "expect", "eof"}
    for s in steps:
        if (
            not isinstance(s, dict)
            or set(s) - {"action", "value", "cols", "rows", "timeout_seconds"}
            or s.get("action") not in allowed_actions
        ):
            raise ValueError("Invalid terminal step")
        act = s["action"]
        if act in {"send", "send_raw", "expect"} and (
            not isinstance(s.get("value"), str) or len(s["value"]) > 4000
        ):
            raise ValueError("Invalid terminal text")
        if act == "resize" and (
            type(s.get("cols")) is not int
            or not 20 <= s["cols"] <= 500
            or type(s.get("rows")) is not int
            or not 5 <= s["rows"] <= 200
        ):
            raise ValueError("Invalid resize dimensions")
        if type(s.get("timeout_seconds", 10)) not in (int, float) or not 0 < s.get("timeout_seconds", 10) <= 60:
            raise ValueError("Invalid terminal timeout")
        if act == "expect":
            re.compile(s["value"])

    cwd = confined(project, task.get("cwd", "."))
    child = pexpect.spawn(
        command,
        args,
        cwd=str(cwd),
        env=_terminal_env(color=color),
        dimensions=(rows, cols),
        encoding="utf-8",
        codec_errors="replace",
        timeout=task.get("step_timeout_ms", 10000) / 1000,
        maxread=4096,
        searchwindowsize=65536,
    )
    records = []
    budget = OutputBudget(limit)
    child.logfile_read = budget
    observed_eof = False
    try:
        for i, s in enumerate(steps):
            action = s["action"]
            status = "passed"
            try:
                if action == "send":
                    child.sendline(s["value"])
                elif action == "send_raw":
                    child.send(s["value"])
                elif action == "resize":
                    child.setwinsize(s["rows"], s["cols"])
                elif action == "expect":
                    child.expect(s["value"], timeout=s.get("timeout_seconds", 10))
                else:
                    child.expect(pexpect.EOF, timeout=s.get("timeout_seconds", 10))
                    observed_eof = True
            except (pexpect.TIMEOUT, pexpect.EOF):
                status = "failed"
            records.append({"step": i + 1, "action": action, "status": status})
            if status == "failed":
                break
    finally:
        child.close(force=True)
    failed = any(s["status"] == "failed" for s in records)
    exit_ok = (child.exitstatus == task.get("expected_exit_code", 0)) if observed_eof else None
    if exit_ok is False:
        failed = True
    atomic_json(output / "terminal-steps.json", records)
    return {
        "backend": "terminal",
        "status": "failed" if failed else "passed",
        "steps": len(steps),
        "executed": len(records),
        "observed_bytes": budget.used,
        "exit_status": child.exitstatus,
        "exit_code_asserted": observed_eof,
        "exit_code_matched": exit_ok,
    }
