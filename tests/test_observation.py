"""Evidence stability must follow rendered geometry, not a ticking clock."""
import copy

import pytest

from testwins.runner import layout_signature
from testwins.observation import assess_stability


def snapshot():
    rect = dict(x=0, y=0, width=100, height=24)
    return dict(viewport=dict(width=400, height=300), document=dict(width=400, height=300),
                nodes=[dict(selector='#clock', rect=rect.copy(), visibleRect=rect.copy())],
                texts=[dict(selector='#clock', text='12:00:00', rect=rect.copy(),
                            visibleRect=rect.copy())])


def test_same_geometry_clock_tick_is_not_layout_movement():
    before = snapshot()
    after = copy.deepcopy(before)
    after['texts'][0]['text'] = '12:00:01'
    assert layout_signature(before) == layout_signature(after)


@pytest.mark.parametrize('surface,field', [
    ('nodes', 'rect'), ('nodes', 'visibleRect'),
    ('texts', 'rect'), ('texts', 'visibleRect'),
])
def test_element_text_or_clip_movement_is_unstable(surface, field):
    before = snapshot()
    after = copy.deepcopy(before)
    after[surface][0][field]['x'] += 10
    assert layout_signature(before) != layout_signature(after)


def test_viewport_change_is_unstable_even_with_fixed_element_geometry():
    before = snapshot()
    after = copy.deepcopy(before)
    after['viewport']['width'] -= 20
    assert layout_signature(before) != layout_signature(after)


@pytest.mark.parametrize('field,value', [
    ('occluded', 5), ('covering', ['#overlay']), ('disabled', True),
    ('inert', True), ('focused', True), ('private', True),
    ('css', {'pointerEvents': 'none'}),
])
def test_equal_geometry_does_not_hide_changed_detector_state(field, value):
    before = snapshot()
    after = copy.deepcopy(before)
    after['nodes'][0][field] = value
    result = assess_stability(before, after)
    assert result['layout'] and not result['state']


def test_content_change_is_explicit_but_not_geometry_or_detector_instability():
    before = snapshot()
    after = copy.deepcopy(before)
    after['texts'][0]['text'] = '12:00:01'
    assert assess_stability(before, after) == {
        'method': 'geometry-and-state/v1', 'layout': True, 'state': True, 'content': False}


def test_clipping_flags_still_invalidate_detector_evidence():
    before = snapshot()
    after = copy.deepcopy(before)
    after['texts'][0]['localClipX'] = True
    result = assess_stability(before, after)
    assert result['layout'] and not result['state']
