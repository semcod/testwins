"""A failed required assertion can never be downgraded by visual deduplication or confidence."""
from __future__ import annotations
from collections import Counter
from typing import Any

KEYS=('cell','repeat','scene','step')


def identity(row: dict) -> tuple:
    return tuple(row[k] for k in KEYS)


def plan_checks(cfg: dict, scenes: list[dict], cells: list[str]) -> list[dict]:
    return [dict(cell=cell,repeat=repeat,scene=scene['id'],step=step['id'], **({'ux_required': True} if 'ux' in step else {}))
            for cell in cells for repeat in range(1,cfg['capture']['repeats']+1)
            for scene in scenes for step in scene.get('steps',[])]


def evaluate(report: dict) -> dict:
    incomplete=[];failures=[]
    if report.get('schema')!='testwins.report/v1':incomplete.append('unsupported_report_schema')
    checks=report.get('checks',[]);plan=report.get('check_plan')
    counts=Counter(c.get('status') for c in checks)
    if not isinstance(plan,list):
        incomplete.append('missing_check_plan');plan=[]
    try:
        expected=[identity(x) for x in plan];actual=[identity(x) for x in checks]
        if len(set(expected))!=len(expected) or len(set(actual))!=len(actual): incomplete.append('duplicate_check_identity')
        if set(expected)!=set(actual):incomplete.append('missing_or_unplanned_check')
    except (KeyError,TypeError):incomplete.append('invalid_check_identity')
    if any(c.get('status') not in ('passed','failed') for c in checks):incomplete.append('blocked_or_unexecuted_required_check')
    if counts['failed']:failures.append('required_assertion_failed')
    ux_expected = {tuple(c.get(k) for k in KEYS) for c in plan if c.get('ux_required') and all(type(c.get(k)) in (str, int) for k in KEYS)}
    for c in checks:
        if all(type(c.get(k)) in (str, int) for k in KEYS) and tuple(c.get(k) for k in KEYS) in ux_expected:
            status = c.get('ux', {}).get('status')
            if status not in ('passed', 'failed'): incomplete.append('ux_not_observed')
            if status == 'failed': failures.append('ux_contract_failed')
    cells=report.get('cells',[])
    cell_plan=report.get('cell_plan')
    if not cells or not isinstance(cell_plan,list) or not cell_plan:incomplete.append('missing_cell_plan_or_execution')
    elif Counter(c.get('id') for c in cells)!=Counter(cell_plan) or len(set(cell_plan))!=len(cell_plan):incomplete.append('cell_plan_mismatch')
    if report.get('coverage',{}).get('state')!='complete' or any(not c.get('complete') for c in cells):incomplete.append('incomplete_observation_scope')
    if report.get('run_gaps'):incomplete.append('run_gaps')
    if report.get('summary',{}).get('confirmed',0):failures.append('confirmed_visual_violation')
    performance=[s['performance'] for s in report.get('snapshots',[]) if s.get('performance')]
    if any(x.get('status')=='incomplete' for x in performance):incomplete.append('performance_not_observed')
    if any(x.get('status')=='failed' for x in performance):failures.append('performance_budget_failed')
    status='incomplete' if incomplete else 'failed' if failures else 'passed'
    return {'schema':'testwins.gate/v1','status':status,'exit_code':{'passed':0,'failed':1,'incomplete':2}[status],
            'expected_checks':len(plan),'passed_checks':counts['passed'],'failed_checks':counts['failed'],
            'blocked_checks':sum(v for k,v in counts.items() if k not in ('passed','failed')),
            'reasons':sorted(set(incomplete+failures)),
            'scope':'all planned mandatory UI assertions, declared budgets and configured visual observations; not universal application correctness'}
