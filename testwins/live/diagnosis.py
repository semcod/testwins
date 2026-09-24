"""Technology-independent hypotheses from rendered geometry, never from imagined source code."""
from __future__ import annotations
import json
from pathlib import Path
from ..model import Finding
from ..util import digest

CATALOG=json.loads(Path(__file__).with_name('catalog.json').read_text('utf-8'))
BY_RULE={r['detection']:r for r in CATALOG['classes'] if r['automatic']}


def enrich(finding: dict, snapshot: dict) -> dict:
    nodes={n['selector']:n for n in snapshot.get('nodes',[])}
    selectors=list(finding.get('selectors',[]))
    related=set(selectors)
    related.update(finding.get('details',{}).get('offenders',[])[:10])
    related.update(finding.get('details',{}).get('covering',[])[:10])
    for s in list(related):related.update(nodes.get(s,{}).get('ancestors',[])[:8])
    evidence=[{'selector':s,'rect':nodes[s].get('rect'),'css':nodes[s].get('css',{}),
               'position':nodes[s].get('position'),'parent':nodes[s].get('parent'),
               'scrollWidth':nodes[s].get('scrollWidth'),'clientWidth':nodes[s].get('clientWidth'),
               'overflowX':nodes[s].get('overflowX'),'overflowY':nodes[s].get('overflowY')}
              for s in sorted(related) if s in nodes][:24]
    hypotheses=[]; rule=finding['rule']
    def add(code,label,score,support,test,repair):
        hypotheses.append({'id':code,'description':label,'support_score':score,'score_kind':'uncalibrated-heuristic-not-probability',
                           'evidence':support,'confirmation_test':test,'repair_direction':repair,'status':'hypothesis'})
    selected=[nodes[s] for s in selectors if s in nodes]
    if rule in {'TW-TEXT-OVERLAP','TW-CONTROL-OCCLUDED','TW-FOCUS-OBSCURED'}:
        abnormal=[e for e in evidence if e['position'] in {'absolute','fixed','sticky'} or e['css'].get('transform','none')!='none']
        if abnormal:add('position-layer','Pozycjonowanie/transformacja lub kontekst warstw może powodować kolizję.',.85,abnormal,
                         'W kopii tego stanu wyłącz jedną transformację/pozycjonowanie i ponów hit-test/geometrię.',
                         'Przywróć przepływ lub popraw lokalny kontekst warstw; nie zwiększaj globalnie z-index bez testu.')
    if rule=='TW-TEXT-CLIPPED':
        clippers=[e for e in evidence if e['overflowX'] in {'hidden','clip'} or e['overflowY'] in {'hidden','clip'}]
        if clippers:add('clipping-ancestor','Obszar przycinania ogranicza widoczny tekst.',.92,clippers,
                         'W odizolowanej kopii zdejmij ograniczenie odpowiedniej osi tylko na podejrzanym przodku.',
                         'Dostosuj rozmiar do treści; zachowaj celowe ellipsis/line-clamp i dostęp do pełnej treści.')
    if rule=='TW-VIEWPORT-OVERFLOW':
        flex=[e for e in evidence if e['css'].get('minWidth')=='auto' and nodes.get(e['parent'],{}).get('display') in {'flex','inline-flex','grid','inline-grid'}]
        if flex:add('min-content','Minimalny rozmiar elementu flex/grid może blokować zmniejszanie.',.83,flex,
                    'Sprawdź min-width:0/minmax(0,1fr) w kopii, przy niezmienionej treści i szerokości.',
                    'Popraw minimalny rozmiar i łamanie tekstu; unikaj maskowania problemu przez overflow-x:hidden.')
        nowrap=[e for e in evidence if e['css'].get('whiteSpace') in {'nowrap','pre'}]
        if nowrap:add('nowrap','Niezawijana zawartość może rozszerzać dokument.',.8,nowrap,
                      'Porównaj white-space:normal/overflow-wrap w kopii z najdłuższym tekstem.',
                      'Dopuść właściwe zawijanie lub lokalne przewijanie przeznaczonego do tego komponentu.')
    if rule.startswith('TW-ALIGNMENT'):
        add('box-spacing','Różne modele pudełka lub odstępy mogą wyjaśniać odchylenie.',.6,evidence,
            'Porównaj margin, padding, border, box-sizing i wyrównanie osi w homologicznych elementach.',
            'Ujednolić regułę komponentu po potwierdzeniu intencji; nie wyrównywać magiczną poprawką pikselową.')
    cat=BY_RULE.get(rule)
    if not hypotheses:
        add('needs-discriminating-test', ' / '.join(cat['possible_causes']) if cat else 'Przyczyna nie została ustalona z dostępnych dowodów.',
            .35,evidence,cat['confirmation'] if cat else 'Odtwórz ten sam stan i dodaj niezależną asercję.',
            'Napraw dopiero po potwierdzeniu przyczyny; nie zakładaj konkretnego frameworka ani błędu backendu.')
    severity={'critical':'P0','high':'P1','normal':'P2','low':'P3'}.get(finding.get('severity'),'P2')
    # Candidates retain impact suggestion, but confidence and priority are separate fields.
    return {**finding,'impact':severity,'detection_confidence':finding.get('confidence',.5),
        'diagnosis':{'authority':'hypothesis-only','technology':'rendered-interface','source_code_inspected':False,
                     'hypotheses':sorted(hypotheses,key=lambda h:-h['support_score']),
                     'limits':['Brak potwierdzenia przyczyny w kodzie aplikacji.','Korelacja nie oznacza przyczynowości.']}}


def supplementary(snapshot: dict, *, stable: bool) -> list[dict]:
    out=[]
    def emit(rule,title,msg,n=None,sev='normal',candidate=True):
        out.append(Finding(rule,title,msg,[n['selector']] if n else ['html'],[n['rect']] if n else [],sev,
                           .65 if candidate else .94,candidate).to_dict())
    if not stable:emit('TW-LAYOUT-UNSTABLE','Obserwacja zmieniła się podczas pomiaru','Geometria lub stan detektorów zmieniły się wokół zrzutu; sprawdź pola stability w dowodzie.')
    if snapshot.get('fontsStatus')!='loaded':emit('TW-FONT-PENDING','Fonty nie są gotowe','Obserwacja stanu fontów, nie diagnoza sieci.')
    visible=[n for n in snapshot.get('nodes',[]) if n['visibleRect']['width']>0 and n['visibleRect']['height']>0]
    if not snapshot.get('texts') and not any(n['tag'] in {'img','canvas','video','svg','iframe','input','button'} for n in visible):
        emit('TW-EMPTY-UI','Potencjalnie pusty interfejs','Brak tekstu i istotnych elementów w obserwowanym widoku. Potrzebny kontrakt oczekiwanej zawartości.')
    for n in visible:
        if n.get('interactive') and not n.get('disabled') and not n.get('inert') and n.get('css',{}).get('pointerEvents')=='none':
            emit('TW-POINTER-DISABLED','Kontrolka ma pointer-events:none','Sprawdź, czy pominięcie wejścia wskaźnika jest celowe.',n)
        if n.get('focused') and n.get('ariaHiddenAncestor'):
            emit('TW-ARIA-HIDDEN-FOCUS','Fokus wewnątrz aria-hidden','Aktywny element znajduje się w semantycznie ukrytym poddrzewie.',n,'high',False)
        if n.get('focused') and n.get('hitSamples') and n.get('occluded',0)/n['hitSamples']>=.6:
            emit('TW-FOCUS-OBSCURED','Fokus na zasłoniętej kontrolce','Hit-test wskazuje obcą warstwę nad aktywnym elementem.',n,'high')
    small=set()
    for t in snapshot.get('texts',[]):
        if 0<t.get('fontSize',99)<10 and t['selector'] not in small:
            n=next((n for n in visible if n['selector']==t['selector']),None)
            if n:emit('TW-TEXT-SMALL','Bardzo mały tekst','Próg heurystyczny 10 CSS px; nie jest to orzeczenie zgodności WCAG.',n,'low');small.add(t['selector'])
    return out


def explain_file(source: Path,output: Path):
    value=json.loads(source.read_text('utf-8'))
    s=value.get('snapshot',value)
    findings=value.get('findings',[])
    if not findings:
        from ..config import load,DEVICES
        from ..detectors import detect
        findings=detect(s,load(),DEVICES['desktop'])+supplementary(s,stable=s.get('stable',True))
    from ..util import atomic_json
    atomic_json(output,{'schema':'testwins.diagnosis/v1','findings':[enrich(f,s) for f in findings]})
