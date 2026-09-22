import copy
from pathlib import Path
import pytest
from testwins.config import load,validate,DEFAULT,MATRICES

def test_default_matrix_is_nine_cells():
    c=load();assert len(MATRICES[c['matrix']])*len(c['devices'])==9

def test_demo_valid():load(Path('configs/demo.yaml'))

@pytest.mark.parametrize('mutate',[
 lambda c:c.update(unknown=True),
 lambda c:c.update(base_url='file:///etc/passwd'),
 lambda c:c['routes'][0].update(path='https://example.com'),
 lambda c:c['capture'].update(repeats=0),
 lambda c:c['capture'].update(repeats=True),
 lambda c:c.update(headless='false'),
 lambda c:c['rules'].update(overlap_fraction=-.5),
 lambda c:c['crawl'].update(enabled=True,allow_paths=[]),
 lambda c:c['suppressions'].append({'rule':'*','reason':'x','expires':'2099-01-01'}),
])
def test_invalid_config(mutate):
    c=copy.deepcopy(DEFAULT);mutate(c)
    with pytest.raises((ValueError,KeyError,TypeError)):validate(c)

def test_mutation_requires_operator_opt_in():
    c=load();c['journeys']=[{'id':'checkout','path':'/','steps':[{'id':'buy','action':'click','selector':'#buy','expect':{'kind':'visible','selector':'#receipt'}}]}]
    with pytest.raises(ValueError,match='allow_mutation'):validate(c)

def test_arbitrary_js_not_in_dsl():
    c=load();c['journeys']=[{'id':'x','path':'/','steps':[{'id':'x','action':'eval','selector':'#x','expect':{'kind':'changed'}}]}]
    with pytest.raises(ValueError,match='arbitrary'):validate(c)
