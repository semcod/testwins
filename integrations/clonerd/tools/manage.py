#!/usr/bin/env python3
"""Migration starter: configure, validate, or run public Testwins 0.4 CLI.

Never launches the application, legacy persona code or API POST requests.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit
import yaml

ROOT = Path(__file__).resolve().parents[1]
AUDITS = [ROOT / 'audit/large.yaml', ROOT / 'audit/mobile.yaml']
JOURNEY = ROOT / 'journeys/developer.desktop.yaml'
WATCH = ROOT / 'testwins.watch.yaml'


def configure(url: str) -> None:
    parts = urlsplit(url)
    if (parts.scheme not in {'http', 'https'} or not parts.hostname or parts.username
            or parts.password or parts.query or parts.fragment or parts.path not in {'', '/'}):
        raise ValueError('Provide an HTTP(S) origin only, without credentials, path or query.')
    # Validate the port before writing anything.
    _ = parts.port
    docs = []
    for path in sorted(ROOT.rglob("*.yaml")):
        if "artifacts" in path.parts:continue
        obj = yaml.safe_load(path.read_text('utf-8'))
        if obj.get('schema')=='testwins.watch/v1':
            for site in obj['sites']:
                site['base_url'] = url.rstrip('/')
        elif obj.get('schema') in {'testwins.config/v1','testwins.api/v1'}:
            obj['base_url'] = url.rstrip('/')
        else:continue
        docs.append((path, obj))
    for path, obj in docs:
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(yaml.safe_dump(obj, allow_unicode=True, sort_keys=False), 'utf-8')
        tmp.replace(path)
    print(json.dumps({'configured_origin': url.rstrip('/'), 'application_started': False}))


def validate() -> dict:
    from testwins import __version__
    from testwins.config import load
    from testwins.live.config import load as load_watch
    audits = [load(p) for p in AUDITS]
    for candidate in sorted(ROOT.rglob('*.yaml')):
        doc=yaml.safe_load(candidate.read_text())
        if isinstance(doc,dict) and doc.get('schema')=='testwins.config/v1':load(candidate)
        elif isinstance(doc,dict) and doc.get('schema')=='testwins.api/v1':
            from testwins.api_contracts import load as load_api
            load_api(candidate)
    j = load(JOURNEY)
    w = load_watch(WATCH, project_root=ROOT)
    result = {'testwins_version': __version__, 'validated_audit_configs': len(audits),
              'validated_example_journeys': len(j['journeys']),
              'persona_scenarios': len(load(ROOT/'journeys/personas.large.yaml')['journeys']),
              'persona_device_combinations': 18, 'live_targets': len(w.targets),
              'read_only_state_device_targets': sum(len(a['routes']) * len(a['devices']) for a in audits),
              'has_real_application_verification': False,
              'scope': 'Python configuration parsers only; selectors and HTTP not exercised'}
    for target in w.targets:
        from urllib.parse import parse_qs
        layout = parse_qs(urlsplit(target.url).query).get('layout')
        expected = ['onepage'] if target.device == 'mobile' else ['desktop']
        if layout != expected:
            raise ValueError('Unexpected mobile/desktop layout mapping')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def scan(matrix: str | None) -> int:
    results = []
    for path in AUDITS:
        cmd = [sys.executable, '-m', 'testwins', 'run', '--config', str(path),
               '--output', str(ROOT / 'artifacts/audit')]
        if matrix:
            cmd += ['--matrix', matrix]
        completed = subprocess.run(cmd, cwd=ROOT, check=False)
        results.append({'config': str(path.relative_to(ROOT)), 'exit_code': completed.returncode})
    # Never discard the first configuration's failure because the second passed.
    codes = [r['exit_code'] for r in results]
    code = 2 if any(c not in (0, 1) for c in codes) else 1 if 1 in codes else 0
    print(json.dumps({'audit_commands': results, 'combined_exit_code': code}))
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    c = subs.add_parser('configure'); c.add_argument('--url', required=True)
    subs.add_parser('validate')
    s = subs.add_parser('scan'); s.add_argument('--matrix', choices=['chromium', 'engines', 'cdp'])
    args = parser.parse_args()
    try:
        if args.command == 'configure': configure(args.url)
        elif args.command == 'validate': validate()
        else: return scan(args.matrix)
        return 0
    except (OSError, ValueError, ImportError, KeyError, TypeError) as exc:
        print(f'migration starter: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
