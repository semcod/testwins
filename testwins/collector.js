/* All inputs are rendered DOM/layout. No application source, network log or private JS state. */
(opts) => {
  const started = performance.now();
  const nodes = [], texts = [], masks = [], gaps = [], links = [];
  const roots = [document]; const seen = new Set();
  let truncated = false;
  const visual=window.visualViewport,ox=visual?.offsetLeft||0,oy=visual?.offsetTop||0;
  const rect = r => ({x:r.x-ox, y:r.y-oy, width:r.width, height:r.height});
  const intersect = (a,b) => {const x=Math.max(a.x,b.x),y=Math.max(a.y,b.y);
    return {x,y,width:Math.max(0,Math.min(a.x+a.width,b.x+b.width)-x),height:Math.max(0,Math.min(a.y+a.height,b.y+b.height)-y)};};
  const vp = {x:0,y:0,width:opts.capture_viewport?.width||visual?.width||innerWidth,height:opts.capture_viewport?.height||visual?.height||innerHeight};
  const parent = el => el.parentElement || (el.getRootNode() instanceof ShadowRoot ? el.getRootNode().host : null);
  const contains = (a,b) => {for(let e=b;e;e=parent(e)) if(e===a) return true; return false;};
  const pathCache = new WeakMap();
  const observedElements = new Map(), hitElements = new WeakMap();
  const path = el => {
    if(!el || el.nodeType!==1) return '';
    if(pathCache.has(el)) return pathCache.get(el);
    const root=el.getRootNode();
    const prefix=root instanceof ShadowRoot ? path(root.host)+' >>> ' : '';
    let p;
    if(el.id && root.querySelectorAll('#'+CSS.escape(el.id)).length===1) p='#'+CSS.escape(el.id);
    else if(el.hasAttribute('data-testid')) p='[data-testid='+JSON.stringify(el.getAttribute('data-testid'))+']';
    else {
      const parts=[]; let e=el;
      while(e && parts.length<12){
        let part=e.localName;
        if(e.parentElement) part+=':nth-of-type('+(Array.from(e.parentElement.children).filter(x=>x.localName===e.localName).indexOf(e)+1)+')';
        parts.unshift(part); if(e===root.documentElement) break; e=e.parentElement;
      } p=parts.join(' > ');
    }
    p=prefix+p;pathCache.set(el,p);return p;
  };
  const isPrivate=el=>{for(let e=el;e;e=parent(e)){
    if(opts.mask_selectors.some(s=>e.matches(s))) return true;
  }return false;};
  const hit=(x,y)=>{let e=document.elementFromPoint(x+ox,y+oy),old=null;
    while(e && e!==old && e.shadowRoot){old=e;e=e.shadowRoot.elementFromPoint(x+ox,y+oy)||e;}return e;};
  // Size potentially exposed by existing scroll ranges, without scrolling the app.
  // Hard clips still constrain the target; a scroll port smaller than the target
  // remains a limit. Hit testing continues to use only the current visibleRect.
  const targetSize=(r,clips)=>{
    const measure=(axis,dimension)=>{
      let start=r[axis],end=start+r[dimension],size=r[dimension];
      for(const c of clips){
        const pos=c.rect[axis],length=c.rect[dimension],overflow=c[axis];
        if(!['hidden','clip','auto','scroll'].includes(overflow))continue;
        const range=c.range[axis];
        if(['auto','scroll'].includes(overflow)&&range>0){
          const offset=c.offset[axis],rtl=axis==='x'&&c.rtl;
          const low=rtl?offset:offset-range,high=rtl?offset+range:offset;
          const shift=Math.max(low,Math.min(high,pos-start));
          size=Math.min(size,Math.max(0,Math.min(end+shift,pos+length)-Math.max(start+shift,pos)));
          // Retain only reachable positions for any outer clip/scroll port.
          start=Math.max(start+low,pos);end=Math.min(end+high,pos+length);
        }else{
          start=Math.max(start,pos);end=Math.min(end,pos+length);
          size=Math.min(size,Math.max(0,end-start));
        }
      }
      return size;
    };
    return {width:measure('x','width'),height:measure('y','height')};
  };
  const scroller=document.scrollingElement,rootStyle=getComputedStyle(document.documentElement);
  const bodyStyle=document.body?getComputedStyle(document.body):rootStyle;
  const pageClip={rect:vp,x:'clip',y:'clip',range:{x:0,y:0},offset:{x:scrollX,y:scrollY},rtl:rootStyle.direction==='rtl'};
  for(const [axis,dimension] of [['x','Width'],['y','Height']]){
    const prop=axis==='x'?'overflowX':'overflowY';
    if(scroller&&!['hidden','clip'].includes(rootStyle[prop])&&!['hidden','clip'].includes(bodyStyle[prop])){
      pageClip[axis]='auto';pageClip.range[axis]=Math.max(0,scroller['scroll'+dimension]-scroller['client'+dimension]);
    }
  }
  for(let ri=0;ri<roots.length;ri++) {
    const root=roots[ri];
    for(const el of root.querySelectorAll('*')) {
      if(seen.has(el))continue;seen.add(el);
      if(seen.size>opts.max_elements*4){truncated=true;break;}
      if(el.shadowRoot) roots.push(el.shadowRoot);
      if(nodes.length>=opts.max_elements){truncated=true;break;}
      const cs=getComputedStyle(el), r=rect(el.getBoundingClientRect());
      if(cs.display==='none'||cs.visibility!=='visible'||+cs.opacity===0||r.width<=0||r.height<=0)continue;
      const interactive=el.matches('button,a[href],input:not([type=hidden]),select,textarea,[role=button],[role=link],[tabindex]');
      let hidden=false, clip={...vp}, intentional=false;
      let stationary=['fixed','sticky'].includes(cs.position)||cs.transform!=='none';
      const targetClips=[];
      const ancestors=[];
      for(let p=parent(el);p;p=parent(p)){
        const pc=getComputedStyle(p);ancestors.push(path(p));
        stationary ||= ['fixed','sticky'].includes(pc.position)||pc.transform!=='none';
        if(+pc.opacity===0||pc.visibility!=='visible'||pc.contentVisibility==='hidden'){hidden=true;break;}
        // Closed <details> can expose descendant Range rects that are not painted.
        // Only its first summary subtree remains rendered; never diagnose hidden answers.
        if(p.localName==='details'&&!p.open){
          const summary=Array.from(p.children).find(c=>c.localName==='summary');
          if(!summary||!contains(summary,el)){hidden=true;break;}
        }
        const pr=rect(p.getBoundingClientRect());
        const c={x:pr.x+p.clientLeft,y:pr.y+p.clientTop,width:p.clientWidth,height:p.clientHeight};
        if(interactive&&p!==scroller)targetClips.push({rect:c,x:pc.overflowX,y:pc.overflowY,
          range:{x:Math.max(0,p.scrollWidth-p.clientWidth),y:Math.max(0,p.scrollHeight-p.clientHeight)},
          offset:{x:p.scrollLeft,y:p.scrollTop},rtl:pc.direction==='rtl'});
        if(['hidden','clip','scroll','auto'].includes(pc.overflowX)){
          const next=intersect(clip,{x:c.x,y:clip.y,width:c.width,height:clip.height});clip.x=next.x;clip.width=next.width;
        }
        if(['hidden','clip','scroll','auto'].includes(pc.overflowY)){
          const next=intersect(clip,{x:clip.x,y:c.y,width:clip.width,height:c.height});clip.y=next.y;clip.height=next.height;
        }
        if(pc.textOverflow==='ellipsis'||parseInt(pc.webkitLineClamp)>0)intentional=true;
      }
      if(hidden)continue;
      const privateNode=isPrivate(el), visibleRect=intersect(r,clip), selector=path(el);
      const n={selector,parent:path(parent(el)),ancestors,tag:el.localName,rect:r,visibleRect,
        targetSize:interactive&&!stationary?targetSize(r,[...targetClips,pageClip]):null,
        display:cs.display,position:cs.position,transform:cs.transform,overflowX:cs.overflowX,overflowY:cs.overflowY,
        clientWidth:el.clientWidth,clientHeight:el.clientHeight,scrollWidth:el.scrollWidth,scrollHeight:el.scrollHeight,
        textOverflow:cs.textOverflow,lineClamp:cs.webkitLineClamp,interactive,
        private:privateNode,disabled:!!el.disabled,inert:el.closest('[inert]')!==null,
        fontSize:parseFloat(cs.fontSize),alignItems:cs.alignItems,flexDirection:cs.flexDirection,
        role:el.getAttribute('role'),name:privateNode?'[REDACTED]':(el.getAttribute('aria-label')||el.getAttribute('alt')||'').slice(0,160),
        brokenImage:el instanceof HTMLImageElement && !!el.currentSrc && el.complete && el.naturalWidth===0,
        occluded:0,hitSamples:0,covering:[],
        focused:el===document.activeElement || el===el.getRootNode().activeElement,
        ariaHiddenAncestor:!!el.closest('[aria-hidden="true"]'),
        css:Object.fromEntries(['minWidth','maxWidth','minHeight','maxHeight','boxSizing','whiteSpace','overflowWrap',
        'wordBreak','lineHeight','fontFamily','zIndex','opacity','transform','pointerEvents','isolation',
        'flexShrink','flexGrow','gap','marginTop','marginRight','marginBottom','marginLeft',
        'paddingTop','paddingRight','paddingBottom','paddingLeft','color','backgroundColor'].map(k=>[k,cs[k]]))};
      observedElements.set(el,n);hitElements.set(el,[]);
      if(privateNode && visibleRect.width && visibleRect.height) masks.push(visibleRect);
      if(interactive && !n.disabled && !n.inert && cs.pointerEvents!=='none' && visibleRect.width>2 && visibleRect.height>2){
        for(const [fx,fy] of [[.5,.5],[.2,.2],[.8,.2],[.2,.8],[.8,.8]]){
          const x=visibleRect.x+visibleRect.width*fx,y=visibleRect.y+visibleRect.height*fy;
          const top=hit(x,y);n.hitSamples++;
          if(top && !contains(el,top) && !contains(top,el)){n.occluded++;n.covering.push(path(top));hitElements.get(el).push(top);}
        }
        n.covering=Array.from(new Set(n.covering));
      }
      if(el.localName==='a'&&el.href&&visibleRect.width>0&&visibleRect.height>0) links.push(el.href);
      if(el.localName==='iframe'&&visibleRect.width>0&&visibleRect.height>0) {
        masks.push(visibleRect);
        const selected=(opts.frame_targets||[]).filter(f=>{try{return el.matches(f.selector);}catch{return false;}});
        gaps.push({kind:'iframe',selector,frame_ids:selected.map(f=>f.id),reason:'Frame interior requires a separately scoped observation; masked in this surface.'});
      }
      if(el.localName==='canvas'&&visibleRect.width>0&&visibleRect.height>0)
        gaps.push({kind:'canvas',selector,reason:'Canvas contents require screenshot interpretation or explicit UI assertions.'});
      nodes.push(n);
      if(privateNode)continue;
      // Direct text nodes only: parent/child DOM rectangles are not mistaken for text collisions.
      for(const child of el.childNodes){
        if(child.nodeType!==Node.TEXT_NODE||!child.textContent.trim())continue;
        const range=document.createRange();range.selectNodeContents(child);
        let ownClip={...clip};
        const border={x:r.x+el.clientLeft,y:r.y+el.clientTop,width:el.clientWidth,height:el.clientHeight};
        const clipX=['hidden','clip'].includes(cs.overflowX),clipY=['hidden','clip'].includes(cs.overflowY);
        if(clipX){const v=intersect(ownClip,{x:border.x,y:ownClip.y,width:border.width,height:ownClip.height});ownClip.x=v.x;ownClip.width=v.width;}
        if(clipY){const v=intersect(ownClip,{x:ownClip.x,y:border.y,width:ownClip.width,height:border.height});ownClip.y=v.y;ownClip.height=v.height;}
        for(const tr of range.getClientRects()){
          if(texts.length>=opts.max_text_rects){truncated=true;break;}
          const rr=rect(tr),vr=intersect(rr,ownClip);
          if(rr.width<1||rr.height<1||vr.width<1||vr.height<1)continue;
          let ancestorClipX=false,ancestorClipY=false;
          let scrollableX=false,scrollableY=false;
          for(let p=parent(el);p;p=parent(p)){const pc=getComputedStyle(p),pr=rect(p.getBoundingClientRect());
            const cx=pr.x+p.clientLeft,cy=pr.y+p.clientTop;
            if(!scrollableX){
              if(['auto','scroll'].includes(pc.overflowX))scrollableX=true;
              else if(['hidden','clip'].includes(pc.overflowX)&&(rr.x<cx-2||rr.x+rr.width>cx+p.clientWidth+2))ancestorClipX=true;
            }
            if(!scrollableY){
              if(['auto','scroll'].includes(pc.overflowY))scrollableY=true;
              else if(['hidden','clip'].includes(pc.overflowY)&&(rr.y<cy-2||rr.y+rr.height>cy+p.clientHeight+2))ancestorClipY=true;
            }
            if(scrollableX && scrollableY)break;
          }
          texts.push({selector,ancestors,rect:rr,visibleRect:vr,text:child.textContent.trim().slice(0,160),
            intentional: intentional||cs.textOverflow==='ellipsis'||parseInt(cs.webkitLineClamp)>0,
            // Clip by viewport is navigation, not a defect. Only local CSS clipping is evaluated below.
            localClipX:ancestorClipX || (clipX && (rr.x<border.x-1||rr.x+rr.width>border.x+border.width+1)),
            localClipY:ancestorClipY || (clipY && (rr.y<border.y-1||rr.y+rr.height>border.y+border.height+1)),
            transformed:cs.transform!=='none',fontSize:parseFloat(cs.fontSize)});
        }
      }
    }
  }
  // Frame pixels can contain private DOM unavailable to this collector.
  // Mask them even after the observation limit, including open shadow trees.
  const privacyRoots=[document];
  for(let i=0;i<privacyRoots.length;i++) for(const el of privacyRoots[i].querySelectorAll('*')) {
    if(el.shadowRoot) privacyRoots.push(el.shadowRoot);
    if(el.localName==='iframe') {
      const r=intersect(rect(el.getBoundingClientRect()),vp);
      if(r.width && r.height) masks.push(r);
    }
  }
  const overlays=(opts.overlays||[]).map(contract=>{
    const result={id:contract.id,state:'invalid',errors:[],trigger:null,overlay:null,background:[],coverage:[]};
    const unique=selector=>{const matches=document.querySelectorAll(selector);
      if(matches.length!==1)throw new Error('Trigger and overlay selectors must each match exactly one element');
      return matches[0];};
    const visible=el=>{const n=observedElements.get(el);return !!n&&n.visibleRect.width>0&&n.visibleRect.height>0;};
    try{
      const trigger=unique(contract.trigger),overlay=unique(contract.overlay),tn=observedElements.get(trigger);
      result.trigger=path(trigger);result.overlay=path(overlay);
      const expanded=trigger.getAttribute('aria-expanded');
      if(!['true','false'].includes(expanded))throw new Error('Trigger needs explicit aria-expanded true/false');
      if(!overlay.id||!(trigger.getAttribute('aria-controls')||'').split(/\s+/).includes(overlay.id))
        throw new Error('Trigger aria-controls must reference the overlay id');
      if(document.querySelectorAll('#'+CSS.escape(overlay.id)).length!==1)
        throw new Error('Overlay id must be unique');
      if(!visible(trigger)||!tn.interactive||tn.disabled||tn.inert||tn.ariaHiddenAncestor||!tn.hitSamples||tn.occluded)
        throw new Error('Trigger must be visible, enabled and reachable');
      if(contains(trigger,overlay)||contains(overlay,trigger))throw new Error('Trigger and overlay must be separate');
      if((expanded==='true')!==visible(overlay))throw new Error('Overlay visibility must agree with aria-expanded');
      const on=observedElements.get(overlay);
      if(expanded==='true'&&(on.inert||on.ariaHiddenAncestor))throw new Error('Active overlay must not be inert or aria-hidden');
      const backgrounds=new Set();
      for(const selector of contract.background){
        const matches=document.querySelectorAll(selector);
        if(!matches.length)throw new Error('Background selector did not match any control');
        for(const el of matches){
          if(!el.matches('button,a[href],input:not([type=hidden]),select,textarea,[role=button],[role=link],[tabindex]'))
            throw new Error('Background selectors must match controls, not containers');
          if(contains(el,trigger)||contains(trigger,el)||contains(el,overlay)||contains(overlay,el))
            throw new Error('Background must exclude the trigger and overlay subtree');
          backgrounds.add(el);
          if(backgrounds.size>128)throw new Error('Background control limit exceeded');
        }
      }
      result.background=Array.from(backgrounds,path);
      result.state=expanded==='true'?'active':'inactive';
      if(result.state==='active')for(const el of backgrounds){
        const n=observedElements.get(el),covers=hitElements.get(el)||[];
        if(n&&n.occluded&&covers.length===n.occluded&&covers.every(top=>contains(overlay,top)))
          result.coverage.push({selector:n.selector,covering:n.covering,occluded:n.occluded,hitSamples:n.hitSamples});
      }
    }catch(error){result.state='invalid';result.coverage=[];result.errors.push(error.name==='SyntaxError'?'Invalid CSS selector':error.message);}
    return result;
  });
  const alignments=opts.alignment.map(a=>({id:a.id,edge:a.edge,tolerance:a.tolerance_px,
    nodes:Array.from(document.querySelectorAll(a.selector)).map(el=>({selector:path(el),rect:rect(el.getBoundingClientRect())})).filter(n=>n.rect.width&&n.rect.height)}));
  const clone=document.documentElement.cloneNode(true);
  // A non-executable semantic serialization, not original HTML/JS source.
  for(const el of clone.querySelectorAll('script,style,link,iframe,object,embed,base,meta,template')) el.remove();
  for(const el of [clone,...clone.querySelectorAll('*')]){
    if(opts.mask_selectors.some(s=>el.matches(s))) {el.textContent='[REDACTED]';el.removeAttribute('value');}
    for(const attr of Array.from(el.attributes)){
      const k=attr.name;
      if(!['id','class','role','type','alt','title','data-testid'].includes(k) && !k.startsWith('aria-')) el.removeAttribute(k);
      else if(/token|secret|password|bearer/i.test(attr.value)&&k!=='type')el.setAttribute(k,'[REDACTED]');
    }
  }
  let html='<!doctype html>\n'+clone.outerHTML;
  if(new TextEncoder().encode(html).length>opts.max_html_bytes){html=new TextDecoder().decode(new TextEncoder().encode(html).slice(0,opts.max_html_bytes));truncated=true;}
  return {schema:'testwins.snapshot/v1',viewport:{width:vp.width,height:vp.height},
    visualViewport:{width:visual?.width||innerWidth,height:visual?.height||innerHeight,offsetX:ox,offsetY:oy,scale:visual?.scale||1},
    layoutViewport:{width:innerWidth,height:innerHeight,rootWidth:document.documentElement.clientWidth,rootHeight:document.documentElement.clientHeight},
    screen:{width:screen.width,height:screen.height},dpr:devicePixelRatio,
    scroll:{x:scrollX+ox,y:scrollY+oy,layoutX:scrollX,layoutY:scrollY},document:{width:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight},
    hasViewportMeta:!!document.querySelector('meta[name=viewport]'),fontsStatus:document.fonts.status,
    title:document.title.slice(0,200),nodes,texts,masks,alignments,overlays,links:Array.from(new Set(links)).slice(0,200),
    gaps,truncated,html,elapsedMs:Math.round(performance.now()-started)};
}
