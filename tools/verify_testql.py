#!/usr/bin/env python3
"""An actual-SDK verification gate for an installed environment; no emulated TestQL."""
from __future__ import annotations
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from testwins.tasks import load_task,run_task
ROOT=Path(__file__).resolve().parents[1]

def main():
    from testql.verification import VerificationRequest,run_verification  # fail closed if unavailable
    root=run_task(load_task(ROOT/'scenarios/shell.task.yaml'),ROOT,ROOT/'verification/testql-runs',trusted_local=True)
    r=json.loads((root/'result.json').read_text())
    print(json.dumps(r,ensure_ascii=False,indent=2))
    assert r['backend']=='testql' and r['status']=='passed' and r['executed']>0,r
    return 0
if __name__=='__main__':raise SystemExit(main())
