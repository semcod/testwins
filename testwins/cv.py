"""Local visual primitives. Detected regions are evidence, never defect verdicts."""
from __future__ import annotations
import math
import os
from pathlib import Path
from typing import Any
from PIL import Image
from .util import file_digest, atomic_json


def read_image(path: Path) -> Image.Image:
    path=path.resolve(strict=True)
    if path.stat().st_size>32*1024*1024:raise ValueError('Image exceeds 32 MiB limit')
    with Image.open(path) as im:
        if im.width*im.height>24_000_000:raise ValueError('Image exceeds pixel limit')
        return im.convert('RGB')


def validate_regions(regions: Any, width: int, height: int) -> list[dict]:
    if not isinstance(regions,list) or len(regions)>1000:raise ValueError('Invalid region count')
    for region in regions:
        if not isinstance(region,dict) or set(region)!={'label','score','box'}:
            raise ValueError('Invalid region fields')
        if not isinstance(region['label'],str) or not 1<=len(region['label'])<=200:
            raise ValueError('Invalid region label')
        if type(region['score']) not in (int,float) or not math.isfinite(region['score']) or not 0<=region['score']<=1:
            raise ValueError('Invalid detector score')
        b=region['box']
        if not isinstance(b,dict) or set(b)!={'x','y','width','height'}:
            raise ValueError('Invalid region box')
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in b.values()):
            raise ValueError('Non-finite region box')
        if b['x']<0 or b['y']<0 or b['width']<=0 or b['height']<=0 or b['x']+b['width']>width+.01 or b['y']+b['height']>height+.01:
            raise ValueError('Region outside image')
    return regions


def iou(a: dict,b: dict) -> float:
    w=max(0,min(a['x']+a['width'],b['x']+b['width'])-max(a['x'],b['x']))
    h=max(0,min(a['y']+a['height'],b['y']+b['height'])-max(a['y'],b['y']))
    intersection=w*h
    union=a['width']*a['height']+b['width']*b['height']-intersection
    return intersection/union if union>0 else 0


def nms(regions: list[dict], threshold: float=.45) -> list[dict]:
    keep=[]
    for item in sorted(regions,key=lambda r:r['score'],reverse=True):
        if all(item['label']!=k['label'] or iou(item['box'],k['box'])<=threshold for k in keep):keep.append(item)
    return keep


def contours(image: Path, *, min_area: int=80, max_regions: int=300) -> list[dict]:
    import cv2
    import numpy as np
    arr=np.array(read_image(image));gray=cv2.cvtColor(arr,cv2.COLOR_RGB2GRAY)
    edges=cv2.Canny(gray,70,160)
    shapes,_=cv2.findContours(edges,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    result=[]
    for shape in shapes:
        x,y,w,h=cv2.boundingRect(shape)
        if w*h>=min_area and w>=4 and h>=4:
            result.append({'label':'visual-region','score':1.0,'box':dict(x=x,y=y,width=w,height=h)})
    # A contour score is constant, not a calibrated probability of a GUI element.
    result=sorted(result,key=lambda r:r['box']['width']*r['box']['height'],reverse=True)[:max_regions]
    return validate_regions(result,arr.shape[1],arr.shape[0])


def match_template(image: Path, template: Path, *, threshold: float=.9) -> dict:
    import cv2
    import numpy as np
    if not 0<=threshold<=1:raise ValueError('Invalid template threshold')
    src=np.array(read_image(image));tpl=np.array(read_image(template))
    if tpl.shape[0]>src.shape[0] or tpl.shape[1]>src.shape[1]:
        return {'found':False,'score':0.0,'box':None}
    if float(tpl.astype(float).std(axis=(0,1)).max())<1.0:raise ValueError('Template must contain texture; uniform images have ambiguous matches')
    heat=cv2.matchTemplate(src,tpl,cv2.TM_CCOEFF_NORMED)
    _,score,_,xy=cv2.minMaxLoc(heat)
    if not math.isfinite(score):raise ValueError('Non-finite template score')
    return {'found':score>=threshold,'score':max(0.,min(1.,float(score))),
            'box':dict(x=xy[0],y=xy[1],width=tpl.shape[1],height=tpl.shape[0])}


def yolo(image: Path, weights: Path, *, trust_model: bool=False, expected_sha256: str | None=None,
         confidence: float=.35, device: str='cpu', tile: int=1280, overlap: int=160,
         factory=None) -> list[dict]:
    """Ultralytics adapter for trusted *local* detection weights. No automatic model download."""
    weights=weights.resolve(strict=True)
    if weights.suffix.lower()!='.pt':raise ValueError('This adapter accepts reviewed local .pt detection weights only')
    if not trust_model:raise ValueError('Loading .pt can execute code; --trust-model is required for reviewed weights')
    if expected_sha256 and file_digest(weights)!=expected_sha256:raise ValueError('Model SHA-256 mismatch')
    if not 0<confidence<=1 or not 256<=tile<=4096 or not 0<=overlap<tile:raise ValueError('Invalid YOLO parameters')
    im=read_image(image)
    if factory is None:
        os.environ.setdefault('YOLO_OFFLINE','true')
        from ultralytics import YOLO
        factory=YOLO
    model=factory(str(weights),task='detect')
    stride=tile-overlap
    xs=list(range(0,max(1,im.width-tile+1),stride));ys=list(range(0,max(1,im.height-tile+1),stride))
    if xs[-1]+tile<im.width:xs.append(max(0,im.width-tile))
    if ys[-1]+tile<im.height:ys.append(max(0,im.height-tile))
    if len(xs)*len(ys)>40:raise ValueError('Too many tiles; crop image or increase tile size')
    output=[]
    for y in ys:
        for x in xs:
            crop=im.crop((x,y,min(x+tile,im.width),min(y+tile,im.height)))
            results=model.predict(source=crop,conf=confidence,device=device,verbose=False,save=False,max_det=300)
            for result in results:
                if result.boxes is None:continue
                for box,score,klass in zip(result.boxes.xyxy.tolist(),result.boxes.conf.tolist(),result.boxes.cls.tolist()):
                    x1,y1,x2,y2=box
                    x1=max(0,min(im.width,x+x1));x2=max(0,min(im.width,x+x2))
                    y1=max(0,min(im.height,y+y1));y2=max(0,min(im.height,y+y2))
                    if x2<=x1 or y2<=y1:continue
                    output.append({'label':str(result.names[int(klass)]),'score':float(score),
                                   'box':dict(x=x1,y=y1,width=x2-x1,height=y2-y1)})
    return validate_regions(nms(output)[:1000],im.width,im.height)


def analyze(image: Path, output: Path, *, backend: str='opencv', weights: Path | None=None,
            trust_model: bool=False, expected_sha256: str | None=None, regions_file: Path | None=None) -> dict:
    im=read_image(image)
    if backend=='opencv':regions=contours(image)
    elif backend=='yolo':
        if not weights:raise ValueError('Provide reviewed local --weights')
        regions=yolo(image,weights,trust_model=trust_model,expected_sha256=expected_sha256)
    elif backend=='regions':
        import json
        if not regions_file or regions_file.stat().st_size>2_000_000:raise ValueError('Provide bounded --regions-json file')
        data=json.loads(regions_file.read_text('utf-8'))
        regions=validate_regions(data['regions'],im.width,im.height)
    else:raise ValueError('Unknown visual backend')
    data={'schema':'testwins.regions/v1','authority':'none','backend':backend,'image_sha256':file_digest(image),
          'image_size':{'width':im.width,'height':im.height},'coordinate_space':'image-pixels',
          'regions':regions,'defects':[], 'note':'Region detection alone is not evidence of a defect.'}
    if weights:data['model_sha256']=file_digest(weights)
    atomic_json(output,data);return data
