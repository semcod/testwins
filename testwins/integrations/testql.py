"""Adapter to TestQL's public, versioned verification contract, never CLI internals."""
from __future__ import annotations
import contextlib
import importlib.metadata
import json
import os
from pathlib import Path
from typing import Any
from ..util import atomic_json, digest

RESULT_SCHEMA = 'testql.verification-result.v1'


def normalize(payload: dict[str, Any], request_hash: str, *, dry_run: bool) -> dict[str, Any]:
    """Validate hashes and accounting; zero tests and skipped execution are not green."""
    if payload.get('schema') != RESULT_SCHEMA:
        raise ValueError('Unsupported TestQL verification contract; upgrade the SDK')
    if payload.get('request_hash') != request_hash or payload.get('dry_run') is not dry_run:
        raise ValueError('TestQL response does not match its request')
    body = {k: v for k, v in payload.items() if k != 'result_hash'}
    if payload.get('result_hash') != digest(body):
        raise ValueError('TestQL result hash mismatch')
    runs = payload.get('runs')
    if not isinstance(runs, list) or payload.get('files') != len(runs):
        raise ValueError('TestQL file accounting mismatch')
    for run in runs:
        for key in ('passed','failed','steps','skipped','validated','executed'):
            if type(run.get(key)) is not int or run[key] < 0:
                raise ValueError('Invalid TestQL counters')
        if type(run.get('ok')) is not bool:
            raise ValueError('Invalid TestQL run status')
    failed_files = sum(not r['ok'] for r in runs)
    if payload.get('failed_files') != failed_files or payload.get('passed_files') != len(runs)-failed_files:
        raise ValueError('TestQL aggregate accounting mismatch')
    if payload.get('ok') is not (failed_files == 0):
        raise ValueError('Contradictory TestQL success flag')
    failed = any(not r['ok'] or r['failed'] or r.get('errors') for r in runs)
    gaps = []
    if not runs: gaps.append('no_scenarios')
    if any(not r['steps'] for r in runs): gaps.append('empty_scenario')
    if not dry_run:
        if any(r['skipped'] for r in runs): gaps.append('skipped_steps')
        if any(r['executed'] == 0 or r['executed'] < r['steps'] for r in runs): gaps.append('unexecuted_steps')
    status = 'failed' if failed else 'incomplete' if gaps else 'validated' if dry_run else 'passed'
    return {'status': status, 'gaps': gaps, 'files': len(runs),
            'steps': sum(r['steps'] for r in runs), 'executed': sum(r['executed'] for r in runs),
            'passed': sum(r['passed'] for r in runs), 'failed': sum(r['failed'] for r in runs),
            'skipped': sum(r['skipped'] for r in runs), 'dry_run': dry_run}


def execute(task: dict, project: Path, output: Path) -> dict:
    try:
        from testql.verification import VerificationRequest, run_verification, verification_contract_schema
    except ImportError as exc:
        raise RuntimeError('Installed TestQL lacks the public verification API. Run make install-testql-source TESTQL_REF=<reviewed-sha>.') from exc
    import jsonschema
    request = VerificationRequest(file_specs=tuple(task['files']), project_dir=str(project),
                                  url=task.get('url','http://sut:8080'), dry_run=task.get('dry_run',False),
                                  quiet=True, timeout=task.get('step_timeout_ms',10000),
                                  allow_semantic_events=False)
    output.mkdir(parents=True, exist_ok=True)
    # The original request/result hashes are preserved. SDK console output is not an interface.
    atomic_json(output/'request.json', request.to_dict())
    with open(os.devnull,'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        result = run_verification(request).to_dict()
    jsonschema.validate(result, verification_contract_schema(RESULT_SCHEMA))
    normalized = normalize(result, request.request_hash, dry_run=request.dry_run)
    atomic_json(output/'testql-result.json', result)
    return {'backend':'testql', 'engine_version':importlib.metadata.version('testql'),
            'engine_contract':RESULT_SCHEMA, 'request_hash':request.request_hash,
            'result_hash':result['result_hash'], **normalized}
