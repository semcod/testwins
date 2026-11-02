"""Skip-free unit and CLI tests for the `testwins tui` subcommand."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from testwins.cli import main


def test_tui_cli_audits_ansi_frame_file_and_writes_report(tmp_path: Path) -> None:
    frame_file = tmp_path / "heyasa_frame.ansi"
    frame_file.write_text(
        "\x1b[2J\x1b[H"
        "\x1b[38;2;56;189;248m┌────────────────────────┐\x1b[0m\r\n"
        "\x1b[38;2;56;189;248m│\x1b[0m\x1b[1;38;2;248;250;252m [1·A] Chat      AUTO   \x1b[0m\x1b[38;2;56;189;248m│\x1b[0m\r\n"
        "\x1b[38;2;56;189;248m└────────────────────────┘\x1b[0m",
        encoding="utf-8",
    )
    out_file = tmp_path / "tui-report.json"

    code = main(
        [
            "tui",
            "--input",
            str(frame_file),
            "--cols",
            "40",
            "--rows",
            "8",
            "--expect-text",
            "[1·A] Chat",
            "--expect-text",
            "AUTO",
            "--palette",
            "#38bdf8",
            "--palette",
            "#f8fafc",
            "--output",
            str(out_file),
        ]
    )
    assert code == 0
    report = json.loads(out_file.read_text(encoding="utf-8"))
    assert report["schema"] == "testwins.tui-report/v1"
    assert report["status"] == "passed"
    assert report["exit_code"] == 0
    assert len(report["boxes"]) == 1
    assert report["boxes"][0]["border_fg"] == "#38bdf8"
    assert report["findings"] == []
    assert report["missing_text"] == []


def test_tui_cli_detects_missing_text_and_palette_drift(tmp_path: Path) -> None:
    frame_file = tmp_path / "drift_frame.ansi"
    frame_file.write_text(
        "\x1b[2J\x1b[H"
        "\x1b[38;2;255;0;0m┌──────────────┐\x1b[0m\r\n"
        "\x1b[38;2;255;0;0m│ [A] Terminal │\x1b[0m\r\n"
        "\x1b[38;2;255;0;0m└──────────────┘\x1b[0m",
        encoding="utf-8",
    )
    out_file = tmp_path / "drift-report.json"

    code = main(
        [
            "tui",
            "--input",
            str(frame_file),
            "--cols",
            "30",
            "--rows",
            "6",
            "--expect-text",
            "[B] Logs",
            "--palette",
            "#38bdf8",
            "--output",
            str(out_file),
        ]
    )
    assert code == 1
    report = json.loads(out_file.read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert report["missing_text"] == ["[B] Logs"]
    rules = {item["rule"] for item in report["findings"]}
    assert "TW-TUI-COLOR-DRIFT" in rules
    assert "TW-TUI-TEXT-MISSING" in rules


def test_tui_cli_executes_pty_command_and_Rejects_invalid_args(tmp_path: Path) -> None:
    out_file = tmp_path / "pty-report.json"
    script = (
        "import sys; "
        "sys.stdout.write('\\x1b[2J\\x1b[H┌────────────┐\\r\\n│ PTY READY  │\\r\\n└────────────┘'); "
        "sys.stdout.flush()"
    )
    code = main(
        [
            "tui",
            "--cols",
            "24",
            "--rows",
            "6",
            "--expect-text",
            "PTY READY",
            "--output",
            str(out_file),
            "--",
            sys.executable,
            "-c",
            script,
        ]
    )
    assert code == 0
    report = json.loads(out_file.read_text(encoding="utf-8"))
    assert report["status"] == "passed"
    assert len(report["boxes"]) == 1

    # Invalid usage (neither --input nor --exec) returns exit code 2
    assert main(["tui"]) == 2
