"""Operator-owned contracts for intentional coverage by a rendered overlay."""
import re

from .model import Finding


def validate_overlays(cfg):
    from .config import closed
    contracts = cfg.get('overlays', [])
    if not isinstance(contracts, list) or len(contracts) > 16:
        raise ValueError('overlays must be a list of at most 16 contracts')
    ids = set()
    for contract in contracts:
        closed(contract, {'id', 'trigger', 'overlay', 'background'}, 'overlay contract')
        ident = contract.get('id')
        if not isinstance(ident, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', ident) or ident in ids:
            raise ValueError('overlay ids must be unique safe identifiers')
        ids.add(ident)
        selectors = contract.get('background')
        if not isinstance(selectors, list) or not 1 <= len(selectors) <= 16:
            raise ValueError('overlay background needs 1–16 explicit control selectors')
        for selector in [contract.get('trigger'), contract.get('overlay'), *selectors]:
            if not isinstance(selector, str) or not selector.strip() or len(selector) > 500:
                raise ValueError('overlay selectors must be nonempty CSS selectors (max 500 characters)')


def assess_overlays(snapshot, cfg):
    """Missing or invalid evidence never authorizes hiding an occlusion."""
    findings, allowed = [], {}
    observed = {o['id']: o for o in snapshot.get('overlays', [])}
    for contract in cfg.get('overlays', []):
        evidence = observed.get(contract['id'])
        if not evidence or evidence['state'] == 'invalid':
            gap = {'kind': 'overlay_contract', 'contract': contract['id'],
                   'reason': 'Declared overlay relationship could not be verified.'}
            if gap not in snapshot.setdefault('gaps', []):
                snapshot['gaps'].append(gap)
            findings.append(Finding(
                'TW-OVERLAY-CONTRACT', 'Invalid overlay contract',
                'The declared trigger, overlay and background relationship could not be verified.',
                [contract['trigger'], contract['overlay']], [], 'high', .99,
                details={'contract': contract['id'], 'errors': (evidence or {}).get('errors', ['missing observation'])}).to_dict())
        elif evidence['state'] == 'active':
            for coverage in evidence['coverage']:
                allowed.setdefault(coverage['selector'], []).append(coverage)
    return findings, allowed
