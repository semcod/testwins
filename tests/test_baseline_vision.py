import pytest
from PIL import Image
from testwins.baseline import compare,baseline_key
from vision import validate_response

def test_equal_pixels(tmp_path):
    a=tmp_path/'a.png';Image.new('RGB',(20,20)).save(a)
    assert compare(a,a,tmp_path/'diff.png')['ratio']==0

def test_different_dimensions(tmp_path):
    a=tmp_path/'a.png';b=tmp_path/'b.png';Image.new('RGB',(20,20)).save(a);Image.new('RGB',(21,20)).save(b)
    assert compare(a,b,tmp_path/'diff.png')['dimensions_changed']

def test_closed_vision_contract():
    p={'findings':[{'category':'spacing','message':'Odstęp jest nierówny','selectors':['#a'],'boxes':[dict(x=0,y=0,width=20,height=20)]}]}
    assert validate_response(p,{'#a'},100,100)
    p['findings'][0]['executor']='shell'
    with pytest.raises(ValueError):validate_response(p,{'#a'},100,100)

def test_vision_cannot_invent_selector():
    p={'findings':[{'category':'other','message':'x','selectors':['#invented'],'boxes':[dict(x=0,y=0,width=20,height=20)]}]}
    with pytest.raises(ValueError):validate_response(p,{'#a'},100,100)

def test_vision_outside_image_rejected():
    p={'findings':[{'category':'other','message':'x','selectors':['#a'],'boxes':[dict(x=95,y=0,width=20,height=20)]}]}
    with pytest.raises(ValueError):validate_response(p,{'#a'},100,100)
