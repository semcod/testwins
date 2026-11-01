"""Unit and PTY integration tests for PyteTerminalSurface and TerminalSession."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from testwins.integrations.terminal import PyteTerminalSurface, TerminalSession, execute
from testwins.tasks import validate_task


def test_pyte_surface_decodes_truecolor_boxes_and_detects_parity_defects() -> None:
    pytest.importorskip("pyte")
    surface = PyteTerminalSurface(cols=40, rows=10)
    # Render a valid 24-bit RGB Heyasa focused pane box (#38bdf8 border, #f8fafc title)
    frame = (
        "\x1b[2J\x1b[H"
        "\x1b[38;2;56;189;248m┌──────────────────┐\x1b[0m\r\n"
        "\x1b[38;2;56;189;248m│\x1b[0m\x1b[1;38;2;248;250;252m [A] Chat         \x1b[0m\x1b[38;2;56;189;248m│\x1b[0m\r\n"
        "\x1b[38;2;56;189;248m└──────────────────┘\x1b[0m"
    )
    surface.feed(frame)

    boxes = surface.detect_boxes()
    assert len(boxes) == 1
    assert boxes[0]["top"] == 0 and boxes[0]["left"] == 0
    assert boxes[0]["width"] == 20 and boxes[0]["height"] == 3
    assert boxes[0]["border_fg"] == "#38bdf8"

    matches = surface.find_text("[A] Chat")
    assert len(matches) == 1
    assert matches[0]["fg"] == "#f8fafc"
    assert matches[0]["bold"] is True

    allowed_heyasa = {"#38bdf8", "#f8fafc", "#0b1020", "#18223a"}
    assert surface.audit_tui_parity(expected_hex_tokens=allowed_heyasa) == []

    # Off-palette RGB color triggers TW-TUI-COLOR-DRIFT
    drift = surface.audit_tui_parity(expected_hex_tokens={"#38bdf8"})
    assert any(f["rule"] == "TW-TUI-COLOR-DRIFT" and f["color"] == "#f8fafc" for f in drift)

    # Broken/clipped box triggers TW-TUI-BOX-BROKEN
    broken = PyteTerminalSurface(cols=24, rows=6)
    broken.feed("\x1b[2J\x1b[H┌──────────\r\n│ Clipped pane")
    defects = broken.audit_tui_parity()
    assert any(f["rule"] == "TW-TUI-BOX-BROKEN" for f in defects)


def test_terminal_session_raw_keys_and_live_pty_resize() -> None:
    pytest.importorskip("pyte")
    script = (
        "import os, shutil, sys, tty\n"
        "tty.setcbreak(sys.stdin.fileno())\n"
        "cols, rows = shutil.get_terminal_size()\n"
        "print(f'INIT:{cols}x{rows}:{os.environ.get(\"COLORTERM\")}', flush=True)\n"
        "ch = sys.stdin.read(1)\n"
        "cols2, rows2 = shutil.get_terminal_size()\n"
        "print(f'KEY:{ord(ch)}:{cols2}x{rows2}', flush=True)\n"
    )
    with TerminalSession(sys.executable, ["-c", script], cols=92, rows=28, color=True) as sess:
        assert sess.wait_for_text("INIT:92x28:truecolor", timeout_s=4.0)
        sess.resize(132, 42)
        sess.send_raw("\x02")  # Ctrl+B prefix without newline!
        assert sess.wait_for_text("KEY:2:132x42", timeout_s=4.0)


def test_execute_supports_send_raw_resize_and_task_validation(tmp_path: Path) -> None:
    child_code = (
        "import shutil, sys, tty\n"
        "tty.setcbreak(sys.stdin.fileno())\n"
        "print('READY', flush=True)\n"
        "b = sys.stdin.read(1)\n"
        "c, r = shutil.get_terminal_size()\n"
        "print(f'GOT:{ord(b)}:{c}x{r}', flush=True)\n"
    )
    task_doc = {
        "schema": "testwins.task/v1",
        "id": "tui-raw",
        "backend": "terminal",
        "cols": 100,
        "rows": 30,
        "color": True,
        "command": sys.executable,
        "args": ["-c", child_code],
        "steps": [
            {"action": "expect", "value": "READY"},
            {"action": "resize", "cols": 110, "rows": 32},
            {"action": "send_raw", "value": "?"},
            {"action": "expect", "value": "GOT:63:110x32"},
            {"action": "eof"},
        ],
    }
    validate_task(task_doc)
    pytest.importorskip("pexpect")
    res = execute(task_doc, tmp_path, tmp_path)
    assert res["status"] == "passed"
    assert res["executed"] == 5
