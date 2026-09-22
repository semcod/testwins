import copy
from testwins.config import load
from testwins.reporting import aggregate,suppression_for
from testwins.model import Finding,identity

def occurrence(repeat=1,cell='chromium-desktop',candidate=False,stable=True):
    f=Finding('TW-TEXT-OVERLAP','Overlap','Observed',['#a','#b'],[],candidate=candidate).to_dict()
    return dict(f,fingerprint=identity('p','home',f),stage='home',cell=cell,repeat=repeat,stable=stable,evidence=[])
def test_requires_two_stable_repetitions():
    c=load();a=occurrence();assert aggregate({'occurrences':[a]},c)[0]['status']=='candidate'
    assert aggregate({'occurrences':[a,occurrence(2)]},c)[0]['status']=='confirmed'
def test_two_browsers_are_not_two_repetitions():
    assert aggregate({'occurrences':[occurrence(),occurrence(cell='edge-desktop')]},load())[0]['status']=='candidate'
def test_unstable_not_confirmed():
    assert aggregate({'occurrences':[occurrence(),occurrence(2,stable=False)]},load())[0]['status']=='candidate'
def test_heuristic_never_auto_confirms():
    assert aggregate({'occurrences':[occurrence(candidate=True),occurrence(2,candidate=True)]},load())[0]['status']=='candidate'
def test_expired_suppression_ignored():
    f={'rule':'TW-X','stage':'home','selectors':['#x']}
    rule={'rule':'TW-*','reason':'test','owner':'qa','expires':'2000-01-01'}
    assert suppression_for(f,[rule]) is None
