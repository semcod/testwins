#!/usr/bin/env python3
"""Verify against an OPERATOR-TRUSTED local wellmanifest/logs checkout.
Imports executable upstream checker code; never take this path from the tested application.
Does not pretend that the adopter implements upstream append services, RPCs or authority.
"""
from __future__ import annotations
import importlib.util
import json
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from testwins.util import atomic_json,file_digest,utc_now
from testwins.verification import verify_run
ROOT=Path(__file__).resolve().parents[1]


def check(run: Path, upstream: Path, out: Path) -> dict:
    local=verify_run(run)
    checker=upstream/'standard/logs_check.py'
    if not checker.is_file():raise ValueError('LOGS_ROOT does not contain standard/logs_check.py')
    spec=importlib.util.spec_from_file_location('testwins_trusted_upstream_logs',checker)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    bundle,contract_sha=module.load_contract(upstream)
    codes={p.stem for p in (ROOT/'errors').glob('*.md')}
    catalog=module.load_error_documents(ROOT,bundle,directory_relative='errors',declared=codes)
    previous='0'*64;prior={};count=0
    from jsonschema import Draft202012Validator,FormatChecker
    validator=Draft202012Validator(bundle['schemas']['event'],format_checker=FormatChecker())
    for count,line in enumerate((run/'logs/audit.jsonl').read_text('utf-8').splitlines(),1):
        event=json.loads(line);validator.validate(event)
        previous=module.validate_event(event,bundle=bundle,catalog=catalog,root=run,path=f'logs/audit.jsonl:{count}',
                         stream='audit',sequence=count,previous_hash=previous,prior_events=prior)
        prior[event['eventId']]=event
    result={'schema':'testwins.logs-conformance/v1','valid':True,'events':count,'error_definitions':len(catalog),
            'contract_sha256':contract_sha,'checker_sha256':file_digest(checker),'checked_at':utc_now(),
            'scope':'upstream event schema + event validator + adopter error documents + local evidence hashes',
            'not_claimed':['RPC/append service compliance','wellmanifest/docs compliance','report signature authenticity'],
            'local':local}
    atomic_json(out,result)
    return result


def main():
    run=os.environ.get('RUN');upstream=os.environ.get('LOGS_ROOT')
    if not run or not upstream:raise ValueError('Set RUN=/path/to/run and LOGS_ROOT=/path/to/trusted/wellmanifest-logs')
    run=Path(run).resolve(strict=True);upstream=Path(upstream).resolve(strict=True)
    out=ROOT/'analysis'/run.name/'logs-conformance.json'
    result=check(run,upstream,out);print(json.dumps(result,ensure_ascii=False,indent=2));return 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:print('conformance:',type(exc).__name__,str(exc),file=sys.stderr);raise SystemExit(2)
