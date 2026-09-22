"""Closed, declarative contracts. No arbitrary page JavaScript or shell in UI YAML."""
from __future__ import annotations
import math
import re
from typing import Any

PERFORMANCE_METRICS = {'Nodes', 'Documents', 'Frames', 'JSEventListeners', 'JSHeapUsedSize',
                       'JSHeapTotalSize', 'LayoutCount', 'RecalcStyleCount', 'LayoutDuration',
                       'RecalcStyleDuration', 'ScriptDuration', 'TaskDuration'}


def _bool(value: Any, label: str) -> None:
    if type(value) is not bool: raise ValueError(label+' must be boolean')


def validate_extensions(cfg: dict) -> None:
    from .config import closed, bounded_int
    sessions=cfg['sessions']
    if not isinstance(sessions,dict) or len(sessions)>100: raise ValueError('Invalid sessions mapping')
    for name,s in sessions.items():
        if not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}',name): raise ValueError('Invalid session id')
        closed(s,{'storage_state'},'session')
        if not isinstance(s.get('storage_state'),str) or not s['storage_state']: raise ValueError('Session needs a local storage_state file')
    if cfg['default_session'] is not None and cfg['default_session'] not in sessions:
        raise ValueError('Unknown default_session')
    d=cfg['downloads']
    _bool(d['enabled'],'downloads.enabled'); _bool(d['retain'],'downloads.retain')
    bounded_int(d['max_bytes'],1,100_000_000,'downloads.max_bytes')
    _bool(cfg['capture']['before_steps'],'capture.before_steps')
    p=cfg['performance']
    _bool(p['enabled'],'performance.enabled'); _bool(p['required'],'performance.required')
    if not isinstance(p['budgets'],dict) or set(p['budgets'])-PERFORMANCE_METRICS:
        raise ValueError('Unsupported CDP performance metric')
    if p['enabled'] and not p['budgets']: raise ValueError('Enabled performance scope needs explicit budgets')
    for value in p['budgets'].values():
        if type(value) not in (int,float) or not math.isfinite(value) or value<0:
            raise ValueError('Performance budget must be finite and non-negative')


def validate_expectation(e: dict) -> None:
    from .config import closed, bounded_int
    closed(e,{'kind','selector','value','name','filename_regex','min_bytes','max_bytes','sha256','starts_with_hex'},'expect')
    kind=e.get('kind')
    supported={'visible','hidden','text','contains_text','count','count_min','url','changed',
               'enabled','disabled','checked','unchecked','focused','value','attribute','download'}
    if kind not in supported: raise ValueError('Unsupported expectation')
    if kind=='download':
        if set(e)-{'kind','filename_regex','min_bytes','max_bytes','sha256','starts_with_hex'}: raise ValueError('Invalid download fields')
        if not isinstance(e.get('filename_regex'),str) or len(e['filename_regex'])>256: raise ValueError('Download needs a filename_regex (up to 256 chars)')
        try:re.compile(e['filename_regex'])
        except re.error as exc:raise ValueError('Invalid filename regular expression') from exc
        bounded_int(e.get('min_bytes',1),1,100_000_000,'min_bytes')
        bounded_int(e.get('max_bytes',10485760),1,100_000_000,'max_bytes')
        if e.get('min_bytes',1)>e.get('max_bytes',10485760): raise ValueError('Download size range reversed')
        if 'sha256' in e and not re.fullmatch('[a-f0-9]{64}',e['sha256']): raise ValueError('Invalid expected SHA-256')
        if 'starts_with_hex' in e:
            if not isinstance(e['starts_with_hex'],str) or not 2<=len(e['starts_with_hex'])<=128: raise ValueError('Invalid magic prefix')
            try: bytes.fromhex(e['starts_with_hex'])
            except ValueError: raise ValueError('Invalid magic prefix') from None
        return
    if set(e)-{'kind','selector','value','name'}: raise ValueError('Download-only fields in UI expectation')
    if kind not in ('url','changed') and not isinstance(e.get('selector'),str): raise ValueError('Expectation selector is required')
    if kind in ('text','contains_text','url','value','attribute') and not isinstance(e.get('value'),str):
        raise ValueError('String expectation value is required')
    if kind=='attribute' and not isinstance(e.get('name'),str): raise ValueError('Attribute name is required')
    if kind in ('count','count_min'): bounded_int(e.get('value'),0,100000,'expected count')
    if kind=='url':
        try:re.compile(e['value'])
        except re.error as exc:raise ValueError('Invalid URL regular expression') from exc
