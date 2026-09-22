"""Hit-tested CDP input. Layout viewport != visual viewport on overflowing mobile documents.
Use genuine browser input, not element.click() or execution of application JavaScript.
"""
from __future__ import annotations
import asyncio

PROBE='''el => {
  const v=visualViewport,ox=v?.offsetLeft||0,oy=v?.offsetTop||0;
  const width=v?.width||innerWidth,height=v?.height||innerHeight;
  const r=el.getBoundingClientRect(),cs=getComputedStyle(el);
  if(el.disabled||el.getAttribute('aria-disabled')==='true'||el.closest('[inert]')||cs.pointerEvents==='none')return null;
  const l=Math.max(r.left,ox),t=Math.max(r.top,oy),right=Math.min(r.right,ox+width),bottom=Math.min(r.bottom,oy+height);
  if(right-l<1||bottom-t<1)return null;
  const composedContains=(p,e)=>{for(let n=e;n;n=n.parentElement||(n.getRootNode() instanceof ShadowRoot?n.getRootNode().host:null))if(n===p)return true;return false;};
  for(const [fx,fy] of [[.5,.5],[.2,.2],[.8,.2],[.2,.8],[.8,.8]]){
    const x=l+(right-l)*fx,y=t+(bottom-t)*fy;
    let top=document.elementFromPoint(x,y),old=null;
    while(top&&top!==old&&top.shadowRoot){old=top;top=top.shadowRoot.elementFromPoint(x,y)||top;}
    if(top&&composedContains(el,top))return {x:x-ox,y:y-oy,rx:r.x,ry:r.y,width:r.width,height:r.height};
  }return null;
}'''


async def pointer(page, cdp, selector: str, *, touch: bool=False, hover: bool=False, timeout_ms: int=8000):
    loc=page.locator(selector)
    await loc.wait_for(state='visible',timeout=timeout_ms)
    await loc.evaluate("el => el.scrollIntoView({block:'center',inline:'nearest',behavior:'instant'})")
    deadline=asyncio.get_running_loop().time()+timeout_ms/1000
    previous=None
    while asyncio.get_running_loop().time()<deadline:
        point=await loc.evaluate(PROBE)
        if point and previous and all(abs(point[k]-previous[k])<.5 for k in ('rx','ry','width','height')):
            if hover:
                await cdp.send('Input.dispatchMouseEvent',{'type':'mouseMoved','x':point['x'],'y':point['y']})
            elif touch:
                await cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':point['x'],'y':point['y'],'radiusX':1,'radiusY':1,'force':1}]})
                await cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
            else:
                for kind in ('mousePressed','mouseReleased'):
                    await cdp.send('Input.dispatchMouseEvent',{'type':kind,'x':point['x'],'y':point['y'],'button':'left','clickCount':1})
            return
        previous=point;await page.wait_for_timeout(80)
    raise TimeoutError('No stable, enabled and unoccluded input point in the visual viewport')


async def scroll_tile(page,cdp,device: dict):
    width,height=device['width'],device['height']
    if cdp:
        await cdp.send('Input.synthesizeScrollGesture',{'x':width*.5,'y':height*.5,'yDistance':-height*.8,
                       'speed':1600,'gestureSourceType':'touch' if device['touch'] else 'mouse','preventFling':True})
    else:
        await page.mouse.move(width*.5,height*.5)
        await page.mouse.wheel(0,height*.8)
    await page.wait_for_timeout(120)
    return await page.evaluate('() => scrollY+(visualViewport?.offsetTop||0)')
