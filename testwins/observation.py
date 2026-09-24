"""Separate rendered geometry, detector state and captured text stability."""
from .util import digest


def _geometry(value):
    if isinstance(value, dict):
        return {k: _geometry(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_geometry(v) for v in value]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return round(value, 1)
    return value


def layout_signature(snapshot: dict) -> str:
    """Include text ranges and clipping, even when the parent box stays fixed."""
    geometry = {k: snapshot.get(k) for k in (
        'viewport', 'visualViewport', 'layoutViewport', 'document', 'scroll',
        'dpr', 'masks', 'alignments')}
    for surface in ('nodes', 'texts'):
        geometry[surface] = [{k: n.get(k) for k in (
            'selector', 'rect', 'visibleRect', 'targetSize')}
            for n in snapshot[surface]]
    return digest(_geometry(geometry))


def assess_stability(before: dict, after: dict) -> dict:
    def state(s):
        result = {k: s.get(k) for k in ('hasViewportMeta', 'fontsStatus', 'truncated', 'gaps')}
        # Retain hit tests, focus, disabled/inert, clipping flags and computed
        # styles. Equal boxes alone do not establish equal detector evidence.
        for surface in ('nodes', 'texts'):
            result[surface] = [{k: v for k, v in n.items()
                                if k not in ('rect', 'visibleRect', 'targetSize', 'text', 'name')}
                               for n in s[surface]]
        return digest(result)

    def content(s):
        return digest([s.get('title'),
                       [(t.get('selector'), t.get('text')) for t in s['texts']],
                       [(n.get('selector'), n.get('name')) for n in s['nodes']]])

    return {'method': 'geometry-and-state/v1',
            'layout': layout_signature(before) == layout_signature(after),
            'state': state(before) == state(after),
            'content': content(before) == content(after)}
