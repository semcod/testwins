import pytest
from testwins.config import load
from testwins.detectors import detect,intersection,from_axe
from testwins.model import identity

def rect(x=0,y=0,w=100,h=20):return dict(x=x,y=y,width=w,height=h)
def text(sel,x=0,y=0,**extra):return dict(selector=sel,rect=rect(x,y),visibleRect=rect(x,y),ancestors=[],text='abc',**extra)
def snapshot(texts=None,nodes=None):return {'viewport':{'width':1000,'height':800},'document':{'width':1000},'hasViewportMeta':True,'nodes':nodes or [],'texts':texts or [],'gaps':[],'alignments':[]}
def rules(s,device='desktop'):c=load();return detect(s,c,c['devices'][device])
def test_text_overlap():assert any(f['rule']=='TW-TEXT-OVERLAP' for f in rules(snapshot([text('#a'),text('#b',50)])))
def test_touching_is_not_overlap():assert not rules(snapshot([text('#a'),text('#b',100)]))
def test_same_owner_is_not_duplicate():assert not rules(snapshot([text('#a'),text('#a',50)]))
def test_ancestor_is_not_text_collision():assert not rules(snapshot([text('#a'),dict(text('#b',50),ancestors=['#a'])]))
def test_transform_remains_candidate():assert rules(snapshot([text('#a',transformed=True),text('#b',50)]))[0]['candidate']
def test_clipping_detected():assert rules(snapshot([text('#x',localClipX=True)]))[0]['rule']=='TW-TEXT-CLIPPED'
def test_ellipsis_not_reported():assert not rules(snapshot([text('#x',localClipX=True,intentional=True)]))
def test_horizontal_overflow():
    s=snapshot();s['document']['width']=1200;assert rules(s)[0]['rule']=='TW-VIEWPORT-OVERFLOW'
def test_missing_viewport_is_candidate():
    s=snapshot();s['hasViewportMeta']=False
    assert rules(s,'mobile')[0]['candidate'];assert not rules(s,'desktop')
def test_alignment_explicit_contract():
    s=snapshot();s['alignments']=[dict(id='a',edge='left',tolerance=2,nodes=[dict(selector='#a',rect=rect()),dict(selector='#b',rect=rect(10))])]
    assert any(f['rule']=='TW-ALIGNMENT' and not f['candidate'] for f in rules(s))
def test_unmatched_alignment_is_gap():
    s=snapshot();s['alignments']=[dict(id='a',edge='left',tolerance=2,nodes=[])]
    assert not rules(s);assert s['gaps'][0]['kind']=='alignment_contract'
def test_axe_does_not_import_html_or_execution_fields():
    r=from_axe({'violations':[{'id':'button-name','impact':'serious','help':'Button name','nodes':[{'target':['#x'],'html':'<script>steal()</script>'}]}]})
    assert r[0]['rule']=='TW-AXE-BUTTON-NAME';assert 'steal' not in str(r)
def test_fingerprint_ignores_geometry_and_order():
    a={'rule':'TW-TEXT-OVERLAP','selectors':['#a','#b'],'rects':[rect()]};b={**a,'selectors':['#b','#a'],'rects':[rect(44)]}
    assert identity('p','home',a)==identity('p','home',b)
    assert identity('p','home',a)!=identity('p','cart',a)

def test_scroll_positions_dedupe_as_same_ui_state():
    f={'rule':'TW-X','selectors':['#a']}
    assert identity('p','home--initial',f)==identity('p','home--scroll-3',f)
    assert identity('p','cart--click',f)!=identity('p','cart--initial',f)
