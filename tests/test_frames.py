import pytest
from testwins.config import load, validate


def config():
    cfg = load()
    cfg['frames'] = [{'id': 'guide', 'selector': '#guide'}]
    cfg['routes'][0]['frames'] = ['guide']
    return cfg


@pytest.mark.parametrize('frames', [None, {}, [{'id':'guide','selector':''}],
    [{'id':'../bad','selector':'iframe'}], [{'id':'guide','selector':'iframe','origin':'*'}],
    [{'id':'guide','selector':'iframe'}]*2])
def test_frame_targets_are_bounded_explicit_and_closed(frames):
    cfg=config();cfg['frames']=frames
    with pytest.raises(ValueError):validate(cfg)


@pytest.mark.parametrize('selected', ['guide', ['missing'], ['guide','guide']])
def test_scene_references_must_resolve(selected):
    cfg=config();cfg['routes'][0]['frames']=selected
    with pytest.raises(ValueError):validate(cfg)


def test_frame_actions_require_scene_opt_in():
    cfg=config();cfg['journeys']=[{'id':'read','path':'/','steps':[
        {'id':'ready','action':'assert','frame':'guide','expect':{'kind':'visible','selector':'body'}}]}]
    with pytest.raises(ValueError,match='selected'):validate(cfg)
    cfg['journeys'][0]['frames']=['guide']
    validate(cfg)
    cfg['journeys'][0]['steps'][0].update(action='goto',value='/',allow_mutation=True)
    with pytest.raises(ValueError,match='not supported'):validate(cfg)
