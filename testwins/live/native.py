from __future__ import annotations
import asyncio
import time
import uuid
from pathlib import Path
from PIL import Image,ImageChops,ImageDraw,ImageStat
from ..util import atomic_json,file_digest
from ..model import Finding
from .diagnosis import enrich


class NativeScanner:
    def __init__(self,cfg,capture=None):self.cfg=cfg;self.capture=capture or self._capture;self.previous={}
    @staticmethod
    def _capture(region):
        import mss
        with mss.mss() as sct:
            shot=sct.grab(region)
            return Image.frombytes('RGB',shot.size,shot.rgb)
    async def start(self):pass
    async def close(self):pass
    async def dirty(self):return []
    async def scan(self,t,tier=1,reason='periodic'):
        start=time.monotonic()
        if tier==0:return {'status':'limited','findings':[],'covered_rules':[],'gaps':[{'kind':'tier_limit'}],'duration_s':0,'tier':0}
        image=await asyncio.to_thread(self.capture,t.region)
        if image.size!=(t.region['width'],t.region['height']):raise ValueError('Capture does not match configured region')
        draw=ImageDraw.Draw(image)
        for r in t.mask_rects:draw.rectangle((r['x'],r['y'],r['x']+r['width'],r['y']+r['height']),fill=(35,35,35))
        dest=self.cfg.output/'evidence'/('scan-'+uuid.uuid4().hex);dest.mkdir(parents=True)
        image.save(dest/'viewport.png');image.save(dest/'annotated.png')
        small=image.resize((96,64));old=self.previous.get(t.id);self.previous[t.id]=small
        f=[];covered=[]
        if old is not None:
            score=sum(ImageStat.Stat(ImageChops.difference(old,small)).mean)/(3*255)
            if score>.035:f.append(Finding('TW-NATIVE-PIXEL-DRIFT','Zmiana w natywnym interfejsie','Zmiana pikseli nie przesądza o błędzie. Brak DOM i informacji o źródłach.', ['screen'],[], 'normal',.5,True,{'difference':score}).to_dict())
            covered.append('TW-NATIVE-PIXEL-DRIFT')
        elif self.cfg.llm['enabled']:
            f.append(Finding('TW-NATIVE-UNASSESSED','Pierwsza obserwacja natywnego GUI','Do weryfikacji względem jawnego celu aplikacji.', ['screen'],[],'low',.3,True).to_dict())
        if t.templates:
            from ..cv import match_template
            for template in t.templates:
                template_path=(self.cfg.root/template['path']).resolve()
                match=await asyncio.to_thread(match_template,dest/'viewport.png',template_path,threshold=template.get('threshold',.95))
                rule='TW-TEMPLATE-EXPECTATION'
                if match['found']!=template.get('present',True):
                    f.append(Finding(rule,'Niespełniony kontrakt wzorca obrazu','Wynik dopasowania odbiega od jawnego kontraktu wzorca.',
                      ['template:'+file_digest(template_path)],[], 'high',.9,False,{'score':match['score'],'threshold':template.get('threshold',.95),'expected_present':template.get('present',True)}).to_dict())
            covered.append('TW-TEMPLATE-EXPECTATION')
        s={'schema':'testwins.native-snapshot/v1','nodes':[],'texts':[],'region':t.region,'masks':list(t.mask_rects),'stable':None,'source':'mss-or-injected-capture'}
        atomic_json(dest/'snapshot.json',s)
        result={'status':'partial','browser':'native','device':'region','site':t.site,'route':'screen','duration_s':time.monotonic()-start,
                'tier':tier,'findings':[enrich(ff,s) for ff in f],'covered_rules':covered,
                'evidence':str(dest.relative_to(self.cfg.output)),'image_sha256':file_digest(dest/'viewport.png'),
                'gaps':[{'kind':'pixel_only','reason':'No DOM geometry, accessibility tree, OS state or source-code diagnosis'}]}
        atomic_json(dest/'scan.json',result)
        atomic_json(dest/'manifest.json',{'schema':'testwins.live-evidence/v1','authority':'none',
            'sha256':{p.name:file_digest(p) for p in dest.iterdir() if p.is_file()}})
        return result


class CompositeScanner:
    def __init__(self,cfg):
        from .scanner import BrowserScanner
        self.web=BrowserScanner(cfg) if any(t.kind=='web' for t in cfg.targets) else None
        self.native=NativeScanner(cfg) if any(t.kind=='desktop' for t in cfg.targets) else None
    async def start(self):
        for s in (self.web,self.native):
            if s:await s.start()
    async def close(self):
        for s in (self.web,self.native):
            if s:await s.close()
    async def dirty(self):return await self.web.dirty() if self.web else []
    async def scan(self,t,tier,reason):return await (self.web if t.kind=='web' else self.native).scan(t,tier,reason)
