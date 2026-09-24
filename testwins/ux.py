"""Operator-selected UX strategies and evidence-bound interaction contracts."""
from __future__ import annotations

import copy
from pathlib import Path

from .model import Finding

STRATEGIES = {
    'dashboard': {'title': 'Dashboard / workspace', 'response_ms': 3000, 'feedback_ms': 700,
                  'patterns': ['visible selection and filters', 'loading and empty states', 'stable navigation', 'progressive disclosure']},
    'form': {'title': 'Form / wizard', 'response_ms': 5000, 'feedback_ms': 1000,
             'patterns': ['inline errors with recovery', 'preserve entered values', 'focus first error', 'explicit success']},
    'commerce': {'title': 'Commerce / checkout', 'response_ms': 5000, 'feedback_ms': 700,
                 'patterns': ['visible cart updates', 'clear total and next step', 'error prevention', 'confirmation before commitment']},
    'content': {'title': 'Content / navigation', 'response_ms': 3000, 'feedback_ms': 1000,
                'patterns': ['information hierarchy', 'predictable links', 'reading continuity', 'search and empty results']},
}
HABITS = {
    'standard': {'think_ms': 0, 'reduced_motion': 'no-preference'},
    'deliberate': {'think_ms': 500, 'reduced_motion': 'no-preference'},
    'keyboard': {'think_ms': 0, 'reduced_motion': 'no-preference'},
    'reduced-motion': {'think_ms': 0, 'reduced_motion': 'reduce'},
}
DEFAULT_UX = {'strategy': None, 'habit': 'standard', 'budgets': {}}
LAYERS = ['functionality', 'graphics', 'information', 'feedback', 'motion']
BUDGETS = {'response_ms', 'feedback_ms', 'motion_ms'}
PROBE = Path(__file__).with_name('ux_probe.js').read_text('utf-8')


def catalog() -> dict:
    return {'schema': 'testwins.ux-strategies/v1', 'strategies': copy.deepcopy(STRATEGIES),
            'habits': copy.deepcopy(HABITS), 'layers': LAYERS,
            'scope': 'Declared simulated habits and explicit contracts; no inference of real human intent.',
            'sources': ['https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html',
                        'https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html',
                        'https://www.nngroup.com/articles/response-times-3-important-limits/']}


def validate_ux(cfg: dict) -> None:
    from .config import closed, bounded_int
    ux = cfg['ux']
    closed(ux, set(DEFAULT_UX), 'ux')
    if ux['strategy'] is not None and ux['strategy'] not in STRATEGIES:
        raise ValueError('Unknown ux.strategy; use testwins strategies')
    if ux['habit'] not in HABITS:
        raise ValueError('Unknown ux.habit')
    closed(ux['budgets'], BUDGETS, 'ux.budgets')
    for key, value in ux['budgets'].items():
        bounded_int(value, 0 if key == 'motion_ms' else 1, 60000, 'ux.' + key)
    contracts = 0
    for scene in cfg['journeys']:
        for step in scene.get('steps', []):
            if 'ux' not in step:
                continue
            contracts += 1
            if ux['strategy'] is None:
                raise ValueError('step.ux requires ux.strategy')
            spec = step['ux']
            closed(spec, {'feedback', 'announce', 'focus', 'visual_change', 'motion'} | BUDGETS, 'step.ux')
            if step['action'] not in {'click', 'fill', 'press', 'hover', 'check', 'select'}:
                raise ValueError('step.ux requires an in-document input action')
            if ux['habit'] == 'keyboard' and step['action'] not in {'press', 'fill', 'select'}:
                raise ValueError('keyboard UX habits require press/fill/select actions')
            if step['expect']['kind'] in {'url', 'download'}:
                raise ValueError('UX probes support in-document transitions only')
            for key in ('focus', 'visual_change', 'motion'):
                if key in spec and (not isinstance(spec[key], str) or not 1 <= len(spec[key]) <= 500):
                    raise ValueError('ux.' + key + ' requires a bounded selector')
            if 'announce' in spec and type(spec['announce']) is not bool:
                raise ValueError('ux.announce must be a boolean')
            if spec.get('announce') and 'feedback' not in spec:
                raise ValueError('ux.announce requires feedback')
            if 'feedback' in spec:
                from .contracts import validate_expectation
                validate_expectation(spec['feedback'])
                if spec['feedback']['kind'] not in {'visible', 'text', 'contains_text', 'attribute'}:
                    raise ValueError('UX feedback needs visible/text/contains_text/attribute expectation')
            for key in BUDGETS & spec.keys():
                bounded_int(spec[key], 0 if key == 'motion_ms' else 1, 60000, 'ux.' + key)
            if 'motion' in spec and cfg['capture']['freeze_animations']:
                raise ValueError('UX motion observation requires capture.freeze_animations: false')
            resolved = contract(cfg, step)
            if max(resolved['response_ms'], resolved['feedback_ms'], resolved['motion_ms']) > cfg['capture']['timeout_ms']:
                raise ValueError('UX budgets must fit capture.timeout_ms')
    if ux['strategy'] is not None and not contracts:
        raise ValueError('ux.strategy requires at least one journey step with ux: {} or a richer contract')


def contract(cfg: dict, step: dict) -> dict | None:
    if 'ux' not in step:
        return None
    ux = cfg['ux']; preset = STRATEGIES[ux['strategy']]
    return {'strategy': ux['strategy'], 'habit': ux['habit'], 'response_ms': preset['response_ms'],
            'feedback_ms': preset['feedback_ms'], 'motion_ms': 0 if ux['habit'] == 'reduced-motion' else 500,
            **ux['budgets'], **step['ux']}


async def start(page, step: dict, spec: dict) -> None:
    await page.evaluate(PROBE, {'action': step['action'], 'selector': step['selector'], 'contract': spec, 'outcome': step['expect']})


async def finish(page, spec: dict, outcome: bool) -> dict:
    # Capture completion before waiting for the feedback/motion observation window.
    raw = await page.evaluate('() => window.__testwinsUX?.complete()')
    if raw is None:
        return incomplete(spec, 'document_replaced_or_probe_missing')
    return assess(spec, raw, outcome)


def incomplete(spec: dict, reason: str) -> dict:
    return {'schema': 'testwins.ux-observation/v1', 'status': 'incomplete',
            'strategy': spec['strategy'], 'habit': spec['habit'], 'reason': reason,
            'violations': [], 'observations': {}}


def assess(spec: dict, raw: dict, outcome: bool) -> dict:
    if not raw.get('input_observed'):
        return incomplete(spec, 'input_event_not_observed')
    if 'motion' in spec and not raw.get('motion_target_observed'):
        return incomplete(spec, 'motion_target_not_observed')
    violations = []
    def fail(rule, layer, message, remedy, selector=None):
        violations.append({'rule': 'TW-UX-' + rule, 'layer': layer, 'message': message,
                           'remediation': remedy, 'selectors': [selector] if selector else []})
    if not outcome:
        fail('OUTCOME', 'functionality', 'Declared outcome was not reached.', 'Restore the declared action-to-result transition and add a regression assertion.')
    elif raw.get('outcome_preexisting') and raw.get('outcome_ms') is None:
        fail('OUTCOME-UNCHANGED', 'functionality', 'The expected result already matched before input and no new matching state was observed.', 'Use an action-specific result or attribute transition that distinguishes the before and after states.')
    elif raw['response_ms'] > spec['response_ms']:
        fail('RESPONSE-LATE', 'functionality', 'Outcome exceeded the configured response budget.', 'Reduce blocking work; verify completion within the explicit budget.')
    if 'feedback' in spec:
        selector = spec['feedback']['selector']
        if raw.get('feedback_ms') is None:
            fail('FEEDBACK-MISSING', 'feedback', 'No new matching feedback followed the input.', 'Show a new, action-specific status or result; an already matching state is insufficient.', selector)
        elif raw['feedback_ms'] > spec['feedback_ms']:
            fail('FEEDBACK-LATE', 'feedback', 'Feedback exceeded the configured budget.', 'Expose pending feedback promptly and keep the result expectation explicit.', selector)
        if spec.get('announce') and raw.get('feedback_ms') is not None and not raw.get('announced'):
            fail('STATUS-SEMANTICS', 'information', 'Matching feedback lacks live-region semantics.', 'Use an appropriate status/alert or aria-live region and verify with assistive technology.', selector)
    if 'focus' in spec and not raw.get('focus_matches'):
        fail('FOCUS', 'information', 'Focus did not reach the declared target.', 'Move or preserve focus according to the declared interaction pattern.', spec['focus'])
    if 'visual_change' in spec and not raw.get('visual_changed'):
        fail('VISUAL-STATE', 'graphics', 'Declared element has no observed visual state change.', 'Make the selected/expanded/pending state perceptible with text or shape as well as color.', spec['visual_change'])
    if 'motion' in spec and (raw.get('infinite_motion') or raw.get('motion_ms', 0) > spec['motion_ms']):
        fail('MOTION-BUDGET', 'motion', 'Observed CSS/Web Animation exceeds the motion budget.', 'Shorten the nonessential animation or honor prefers-reduced-motion.', spec['motion'])
    layers = ['functionality']
    for field, layer in [('feedback', 'feedback'), ('announce', 'information'), ('focus', 'information'), ('visual_change', 'graphics'), ('motion', 'motion')]:
        if spec.get(field) and layer not in layers: layers.append(layer)
    return {'schema': 'testwins.ux-observation/v1', 'status': 'failed' if violations else 'passed',
            'strategy': spec['strategy'], 'habit': spec['habit'], 'observations': raw,
            'budgets': {k: spec[k] for k in sorted(BUDGETS)}, 'violations': violations,
            'assessed_layers': layers, 'unobserved_layers': [x for x in LAYERS if x not in layers],
            'scope': 'Input-to-observation timing includes browser sampling/automation overhead; not INP or proof of causality.'}


def findings(result: dict) -> list[dict]:
    return [Finding(v['rule'], v['message'], v['remediation'], v['selectors'], [], 'normal', .99,
                    details={'layer': v['layer'], 'strategy': result['strategy'],
                             'observations': result['observations']}).to_dict() for v in result['violations']]
