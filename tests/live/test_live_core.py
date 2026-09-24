import asyncio
import copy
import importlib.util
import json
import time
from pathlib import Path
import pytest
import yaml
from testwins.live.config import load,Target,WatchConfig,affected
from testwins.live.policy import Resources,Governor,capacity
from testwins.live.store import Store
from testwins.live.runtime import Changes,Lease,Monitor
from testwins.live.diagnosis import enrich,supplementary,CATALOG


def raw(pages=None):
    return {'schema':'testwins.watch/v1','project':'example','sites':[{'id':'app','base_url':'http://localhost:8080',
        'pages':pages or ['/'],'devices':['desktop'],'browsers':['chromium']}], 'resources':{'poll_s':.1}}

def config(tmp_path,value=None):
    p=tmp_path/'watch.yaml';p.write_text(yaml.safe_dump(value or raw()));return load(p)

def finding(candidate=False,rule='TW-TEXT-OVERLAP'):
    return {'rule':rule,'title':'Overlap','message':'Measured overlap','selectors':['#a','#b'],'rects':[],
            'candidate':candidate,'confidence':.9,'severity':'high','impact':'P1'}

def result(fs=None,covered=None,complete=True,evidence=''):
    return {'status':'complete' if complete else 'incomplete','findings':fs or [],
            'covered_rules':['TW-TEXT-OVERLAP'] if covered is None else covered,'gaps':[], 'evidence':evidence,'duration_s':.01,'tier':1}


def test_inventory_300_routes_2700_cells(tmp_path):
    v=raw(['/p/'+str(i) for i in range(300)]);v['sites'][0]['browsers']=['chromium','firefox','webkit'];v['sites'][0]['devices']=['desktop','tablet','mobile']
    c=config(tmp_path,v);assert len(c.targets)==2700;assert len({t.id for t in c.targets})==2700

@pytest.mark.parametrize('change',[
 lambda v:v.update(unknown=True),lambda v:v['resources'].update(max_workers=0),lambda v:v['resources'].update(cpu_limit=float('nan')),
 lambda v:v['sites'][0].update(pages=['https://evil.test/']),lambda v:v['sites'][0].update(pages=['/?token=secret']),
 lambda v:v['sites'][0].update(browsers=['safari']),lambda v:v.update(watch={'paths':['../../secret']}),
 lambda v:v.update(llm={'enabled':'yes'}),lambda v:v['sites'][0].update(pages=['/','/']),
 lambda v:v['sites'][0].update(pages=[{'path':'/','expect':[{'kind':'click','selector':'button'}]}]),
 lambda v:v.update(screens=[{'id':'screen','region':{'left':0,'top':0,'width':100,'height':100}}]),
])
def test_invalid_config_rejected(tmp_path,change):
    v=raw();change(v)
    with pytest.raises((ValueError,KeyError)):config(tmp_path,v)


def test_defaults_no_paid_models(tmp_path):
    c=config(tmp_path);assert c.llm['enabled'] is False;assert c.max_tier==2
    assert c.targets[0].audit['axe']['enabled'] is False


def test_native_region_requires_consent(tmp_path):
    v=raw();v['sites']=[];v['screens']=[{'id':'test','allow_desktop_capture':True,'region':{'left':0,'top':0,'width':100,'height':100}}]
    c=config(tmp_path,v);assert c.targets[0].kind=='desktop'
    v['screens'][0]['mask_rects']=[{'x':80,'y':0,'width':50,'height':10}]
    with pytest.raises(ValueError):config(tmp_path,v)


def test_file_route_mapping(tmp_path):
    t=Target('a','app','http://localhost','home',source_globs=('src/header.*',))
    assert affected(t,['src/header.css']);assert not affected(t,['src/footer.css'])


def test_scope_changes_with_device_config(tmp_path):
    t=config(tmp_path).targets[0];s=t.scope;t.audit['color_scheme']='dark';assert t.scope!=s


def test_governor_conservative(tmp_path):
    c=config(tmp_path);c.max_workers=8;g=Governor(c)
    r=Resources(10,8192,4,50000);assert g.decide(r)['workers']==4
    low=Resources(10,128,4,50000);assert g.decide(low)['workers']==0
    disk=Resources(10,8192,4,0);assert g.decide(disk)['workers']==0


def test_governor_cpu_hysteresis(tmp_path):
    c=config(tmp_path);g=Governor(c)
    for _ in range(4):d=g.decide(Resources(99,8192,4,50000))
    assert d['workers']==0;assert d['tier']<=1
    assert g.decide(Resources(1,8192,4,50000))['workers']==0
    for _ in range(15):d=g.decide(Resources(1,8192,4,50000))
    assert d['workers']==4


def test_capacity_is_analytic():
    a=capacity(2700,2,6,60);assert a['ideal_cycle_s']==900;assert not a['feasible_at_ideal_utilization']


def test_confirm_and_recover_are_hysteretic(tmp_path):
    s=Store(tmp_path/'db')
    try:
        e=s.record('t','scope',result([finding()]),now=10);assert any(x['kind']=='incident_opened' for x in e)
        assert s.status()['totals']['observed']==1
        e=s.record('t','scope',result([finding()]),now=11);assert any(x['kind']=='incident_confirmed' for x in e)
        assert not s.record('t','scope',result([finding()]),now=12)
        s.record('t','scope',result(covered=[],complete=False),now=13);assert s.status()['totals']['confirmed']==1
        s.record('t','scope',result(),now=14);assert s.status()['totals']['confirmed']==1
        e=s.record('t','scope',result(),now=15);assert any(x['kind']=='incident_resolved' for x in e)
        e=s.record('t','scope',result([finding()]),now=16);assert any(x['kind']=='incident_reopened' for x in e)
        assert s.status()['totals']['observed']==1
    finally:s.close()


def test_candidates_never_self_confirm(tmp_path):
    s=Store(tmp_path/'db')
    try:
        for _ in range(6):s.record('t','scope',result([finding(True)]))
        assert s.status()['totals'].get('confirmed',0)==0;assert s.status()['totals']['candidate']==1
    finally:s.close()


def test_new_scope_does_not_resolve_old_evidence(tmp_path):
    s=Store(tmp_path/'db')
    try:
        for _ in range(2):s.record('t','scope1',result([finding()]))
        for _ in range(3):s.record('t','scope2',result())
        assert s.status()['totals']['confirmed']==1
    finally:s.close()


def test_incompleteness_cannot_be_recovery(tmp_path):
    s=Store(tmp_path/'db')
    try:
        for _ in range(2):s.record('t','scope',result([finding()]))
        for _ in range(10):s.record('t','scope',result(covered=[],complete=False))
        assert s.status()['totals']['confirmed']==1
    finally:s.close()


def test_confirmed_proof_survives_uncertain_observation(tmp_path):
    s=Store(tmp_path/'db')
    try:
        for _ in range(2):s.record('t','scope',result([finding()],evidence='original'))
        s.record('t','scope',result([finding(True)],covered=[],evidence='uncertain'))
        row=s.status()['incidents'][0];assert row['evidence']=='original';assert row['detail']['candidate'] is False
    finally:s.close()


def test_browser_cells_are_independent(tmp_path):
    s=Store(tmp_path/'db')
    try:
        for _ in range(2):s.record('chrome','scope',result([finding()]))
        for _ in range(4):s.record('firefox','scope',result())
        assert s.status()['totals']['confirmed']==1
    finally:s.close()


def test_llm_rolling_budget_persists_and_counts_failure(tmp_path):
    path=tmp_path/'db';s=Store(path)
    cid,why=s.reserve_call('x','t',1,60,now=1000);assert cid
    s.finish_call(cid,'failed',{});s.close();s=Store(path)
    try:
        assert s.reserve_call('y','t2',1,60,now=1001)[1]=='hourly_budget'
        assert s.reserve_call('y','t2',1,60,now=4601)[0]
    finally:s.close()


def test_llm_duplicate_inflight_and_cache(tmp_path):
    s=Store(tmp_path/'db')
    try:
        cid,_=s.reserve_call('x','a',10,60,now=1000);assert cid
        assert s.reserve_call('y','b',10,60,now=1001)[1]=='inflight_limit'
        s.finish_call(cid,'completed',{})
        assert s.reserve_call('x','c',10,60,now=1100)[1]=='cached_or_recently_attempted'
        assert s.reserve_call('z','a',10,600,now=1100)[1]=='cooldown'
    finally:s.close()


def test_event_sequence_survives_retention(tmp_path):
    s=Store(tmp_path/'db',keep_events=100)
    try:
        for i in range(130):s.emit('test',{'i':i})
        lo,hi=s.event_bounds();assert (lo,hi)==(31,130)
        assert s.events(125)[0]['id']==126
    finally:s.close()


def test_latency_needs_history(tmp_path):
    s=Store(tmp_path/'db')
    try:
        assert s.latency_anomaly('t',99) is None
        for i in range(10):s.record('t','s',dict(result(),duration_s=1),now=i)
        assert s.latency_anomaly('t',10)['kind']=='observer_latency_anomaly'
    finally:s.close()


def test_file_watch_ignores_artifacts_and_secrets(tmp_path):
    c=config(tmp_path);c.watch_paths=['.'];w=Changes(c);w.poll()
    (tmp_path/'x.css').write_text('a{}');(tmp_path/'.env').write_text('SECRET=1');c.output.mkdir(parents=True);(c.output/'events.json').write_text('{}')
    assert w.poll()==['x.css']
    (tmp_path/'x.css').unlink();assert w.poll()==['x.css']


def test_output_lease(tmp_path):
    with Lease(tmp_path/'lock'):
        with pytest.raises(RuntimeError):
            with Lease(tmp_path/'lock'):pass
    with Lease(tmp_path/'lock'):pass


def test_catalog_honest_and_unique():
    assert CATALOG['exhaustive'] is False;rows=CATALOG['classes'];assert len(rows)==96
    assert len({r['id'] for r in rows})==96
    assert sum(r['automatic'] for r in rows)==22


def test_root_cause_min_content_not_source_blame():
    nodes=[{'selector':'#grid','parent':'html','display':'flex','rect':{},'css':{},'ancestors':[]},
           {'selector':'#a','parent':'#grid','display':'block','rect':{},'css':{'minWidth':'auto','whiteSpace':'nowrap'},'ancestors':['#grid']}]
    f=finding(rule='TW-VIEWPORT-OVERFLOW');f['details']={'offenders':['#a']}
    d=enrich(f,{'nodes':nodes})['diagnosis'];assert d['source_code_inspected'] is False
    assert 'min-content' in [x['id'] for x in d['hypotheses']]
    assert all(h['score_kind'].endswith('not-probability') for h in d['hypotheses'])


class FakeScanner:
    def __init__(self,delay=.001):self.active=0;self.maximum=0;self.seen=[];self.closed=False;self.delay=delay
    async def start(self):pass
    async def close(self):self.closed=True
    async def dirty(self):return []
    async def scan(self,t,tier,reason):
        self.active+=1;self.maximum=max(self.maximum,self.active);self.seen.append(t.id)
        await asyncio.sleep(self.delay);self.active-=1
        return result()


def test_scheduler_bounded_parallelism_and_inventory(tmp_path):
    c=config(tmp_path);c.targets=[Target('t'+str(i),'s',f'http://app{i}.test/','home',audit={}) for i in range(30)]
    c.max_workers=3;c.poll_s=.001;s=Store(c.output/'db');scanner=FakeScanner(.005)
    try:
        m=Monitor(c,scanner,s,resource_sampler=lambda _:Resources(1,32768,8,100000))
        asyncio.run(m.run(once=True));assert len(set(scanner.seen))==30;assert scanner.maximum<=3;assert scanner.closed
    finally:s.close()


def test_request_coalescing_keeps_latest_change(tmp_path):
    c=config(tmp_path);s=Store(c.output/'db')
    try:
        m=Monitor(c,FakeScanner(),s);tid=c.targets[0].id
        for _ in range(500):m.request([tid],'source')
        assert len(m.pending)==1;assert m.generation[tid]==500
    finally:s.close()


def test_coverage_gap_breaks_confirmation_and_recovery_streaks(tmp_path):
    s=Store(tmp_path/'db')
    try:
        s.record('t','s',result([finding()]))
        s.record('t','s',result(covered=[],complete=False))
        s.record('t','s',result([finding()]))
        assert s.status()['incidents'][0]['state']=='observed'
        s.record('t','s',result([finding()]))
        assert s.status()['incidents'][0]['state']=='confirmed'
        s.record('t','s',result())
        s.record('t','s',result(covered=[],complete=False))
        s.record('t','s',result())
        assert s.status()['incidents'][0]['state']=='confirmed'
        s.record('t','s',result())
        assert s.status()['totals']['resolved']==1
    finally:s.close()


def test_retention_includes_model_bundles_and_respects_inflight_pins(tmp_path):
    from testwins.live.runtime import Retention
    c=config(tmp_path);c.evidence_limit_mb=1;s=Store(c.output/'db')
    try:
        for rel in ('evidence/old','augmentations/old','augmentations/inflight'):
            p=c.output/rel;p.mkdir(parents=True);(p/'data').write_bytes(b'x'*500000)
        re=Retention(c,s);assert re.maintain(force=True,extra_protected={'augmentations/inflight'})
        assert (c.output/'augmentations/inflight/data').exists()
        assert re.last_total<1048576
        assert not (c.output/'evidence/old').exists()
    finally:s.close()


def test_retention_pauses_instead_of_deleting_active_incident_proof(tmp_path):
    from testwins.live.runtime import Retention
    c=config(tmp_path);c.evidence_limit_mb=1;s=Store(c.output/'db')
    try:
        p=c.output/'evidence/pinned';p.mkdir(parents=True);(p/'data').write_bytes(b'x'*1200000)
        s.record('t','s',result([finding()],evidence='evidence/pinned'))
        assert Retention(c,s).maintain(force=True) is False
        assert p.exists()
    finally:s.close()


def test_distinct_contracts_on_same_selector_do_not_merge(tmp_path):
    s=Store(tmp_path/'db')
    try:
        fs=[dict(finding(rule='TW-EXPECTATION'),details={'contract_id':key}) for key in ('visible','text')]
        for _ in range(2):s.record('t','s',result(fs,covered=['TW-EXPECTATION']))
        assert s.status()['totals']['confirmed']==2
    finally:s.close()
