"""Explicit, surface-scoped contracts for text scrolled behind opaque headers."""
import re

from .model import Finding


def validate_sticky_regions(cfg):
    from .config import closed
    regions = cfg.get('sticky_regions', [])
    if not isinstance(regions, list) or len(regions) > 16:
        raise ValueError('sticky_regions must be a list of at most 16 contracts')
    ids = set()
    frames = {f['id'] for f in cfg.get('frames', [])}
    for region in regions:
        closed(region, {'id', 'selector', 'content', 'frame'}, 'sticky region')
        ident = region.get('id')
        if not isinstance(ident, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', ident) or ident in ids:
            raise ValueError('sticky region ids must be unique safe identifiers')
        ids.add(ident)
        for key in ('selector', 'content'):
            if not isinstance(region.get(key), str) or not region[key].strip() or len(region[key]) > 500:
                raise ValueError('sticky region selectors must be nonempty (max 500 characters)')
        if 'frame' in region and (not isinstance(region['frame'], str) or region['frame'] not in frames):
            raise ValueError('sticky region frame must reference a configured frame')


def scoped_regions(cfg, scope):
    frame = scope.get('id') if scope.get('kind') == 'frame' else None
    return [r for r in cfg.get('sticky_regions', []) if r.get('frame') == frame]


def assess_sticky_regions(snapshot, cfg):
    """Only fresh, bound collector evidence can remove a text range from overlap tests."""
    findings, hidden = [], set()
    for contract in scoped_regions(cfg, snapshot.get('scope', {})):
        matches = [r for r in snapshot.get('sticky_regions', []) if r.get('id') == contract['id']]
        evidence = matches[0] if len(matches) == 1 else None
        valid = (evidence and evidence.get('state') in ('active', 'inactive')
                 and evidence.get('selector') == contract['selector']
                 and evidence.get('content') == contract['content'])
        if not valid:
            gap = {'kind': 'sticky_contract', 'contract': contract['id'],
                   'reason': 'Declared opaque sticky region could not be verified.'}
            if gap not in snapshot.setdefault('gaps', []): snapshot['gaps'].append(gap)
            findings.append(Finding('TW-STICKY-CONTRACT', 'Unverified sticky region',
                gap['reason'], [contract['selector'], contract['content']], [], 'high', .99,
                details={'contract': contract['id'], 'errors': (evidence or {}).get('errors', ['missing observation'])}).to_dict())
        elif evidence['state'] == 'active' and snapshot.get('stable') is not False:
            for coverage in evidence.get('coverage', []):
                index = coverage.get('text_index')
                if type(index) is not int or not 0 <= index < len(snapshot['texts']): continue
                text = snapshot['texts'][index]
                if (text.get('protectedFromSticky', True) is False
                        and coverage.get('selector') == text['selector']
                        and coverage.get('rect') == text['rect']
                        and coverage.get('hit_samples') == 5):
                    hidden.add(index)
    return findings, hidden
