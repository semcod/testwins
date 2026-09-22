"""Optional read-only CDP lookup of rendered stylesheet locations, not repository blame."""
from __future__ import annotations
from ..util import redact_url

PROPERTIES={'width','height','min-width','max-width','min-height','max-height','position','z-index','overflow','overflow-x','overflow-y',
            'transform','display','white-space','word-break','overflow-wrap','line-height','font-size','box-sizing','flex','flex-shrink','grid-template-columns',
            'margin','margin-left','margin-right','margin-top','margin-bottom','padding','gap','align-items','justify-content','pointer-events'}


async def inspect(cdp,selectors):
    if cdp is None:return {'status':'unavailable','reason':'CSS provenance requires CDP','nodes':[]}
    headers={}
    def added(event):
        h=event.get('header',{});headers[h.get('styleSheetId')]=h
    cdp.on('CSS.styleSheetAdded',added)
    result=[];gaps=[]
    try:
        await cdp.send('DOM.enable');await cdp.send('CSS.enable')
        document=await cdp.send('DOM.getDocument',{'depth':0,'pierce':False})
        for selector in list(dict.fromkeys(selectors))[:12]:
            if '>>>' in selector or len(selector)>500:gaps.append('unsupported_or_long_selector');continue
            try:
                node=await cdp.send('DOM.querySelector',{'nodeId':document['root']['nodeId'],'selector':selector})
                if not node.get('nodeId'):continue
                styles=await cdp.send('CSS.getMatchedStylesForNode',{'nodeId':node['nodeId']});matches=[]
                for match in styles.get('matchedCSSRules',[])[:16]:
                    rule=match['rule'];style=rule.get('style',{});sheet=headers.get(style.get('styleSheetId'),{})
                    props=[{'name':p['name'],'value':p.get('value','')[:300],'important':bool(p.get('important',False))}
                           for p in style.get('cssProperties',[]) if p.get('name') in PROPERTIES and p.get('parsedOk',True) and not p.get('disabled',False)]
                    if not props:continue
                    # Do not carry arbitrary CSS url() or credential-bearing source URLs.
                    props=[p for p in props if 'url(' not in p['value'].lower()]
                    r=style.get('range',{})
                    matches.append({'selector':rule.get('selectorList',{}).get('text','')[:500],
                        'served_stylesheet':redact_url(sheet.get('sourceURL','')),'line_1based':r.get('startLine',0)+1 if r else None,
                        'properties':props[:24],'origin':rule.get('origin','unknown')})
                result.append({'selector':selector,'matched_rules':matches})
            except Exception as exc:gaps.append(type(exc).__name__)
        return {'status':'matched-declarations-not-proven-cause','nodes':result,'gaps':gaps,
                'limits':['Matched does not mean winning CSS declaration.','Served CSS location may be generated/minified; no source-map/repository lookup.']}
    finally:
        cdp.remove_listener('CSS.styleSheetAdded',added)
