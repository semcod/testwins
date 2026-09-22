"""Explicit bridge: pytest -p testwins.pytest_plugin. No automatic scans or host-side actions."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path
import pytest


@pytest.fixture
def testwins_assert_report():
    def verify(path: str | Path):
        from .gate import evaluate
        from .verification import verify_run
        root=Path(path)
        if root.is_dir():verify_run(root);root=root/'report.json'
        report=json.loads(root.read_text('utf-8'));gate=evaluate(report)
        assert gate['exit_code']==0, json.dumps(gate,ensure_ascii=False)
        return report
    return verify


@pytest.fixture
def testwins_run(tmp_path, testwins_assert_report):
    def execute(config: str | Path, *, url: str | None = None):
        output=tmp_path/'testwins'
        cmd=[sys.executable,'-m','testwins','run','--config',str(config),'--output',str(output)]
        if url:cmd.extend(['--url',url])
        done=subprocess.run(cmd,check=False,timeout=3600,capture_output=True,text=True)
        latest=output/'latest.json'
        if not latest.exists():pytest.fail(f'Testwins did not create a report (exit {done.returncode}); inspect local config/browser availability')
        name=json.loads(latest.read_text())['directory']
        root=(output/name).resolve()
        if not root.is_relative_to(output.resolve()):pytest.fail('Invalid Testwins output pointer')
        report=testwins_assert_report(root)
        assert done.returncode==0, 'CLI exit did not agree with the report'
        return report
    return execute
