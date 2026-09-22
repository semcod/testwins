from __future__ import annotations
import copy
import fnmatch
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import yaml
from ..config import DEVICES, MATRICES, load as audit_load
from ..util import origin, digest


def number(v, lo, hi, name, integer=False):
    if type(v) not in ((int,) if integer else (int,float)) or not math.isfinite(v) or not lo <= v <= hi:
        raise ValueError(f'{name} must be {lo}..{hi}')
    return v


def closed(v, keys, label):
    if not isinstance(v, dict) or set(v)-set(keys):
        raise ValueError(f'Unknown fields or invalid object in {label}')


@dataclass(frozen=True)
class Target:
    id: str
    site: str
    url: str
    route: str
    browser: str = 'chromium'
    device: str = 'desktop'
    interval_s: float = 60
    priority: int = 2
    hot: bool = False
    expect: tuple = ()
    source_globs: tuple = ()
    audit: dict = field(default_factory=dict, compare=False)
    kind: str = 'web'
    region: dict = field(default_factory=dict, compare=False)
    mask_rects: tuple = ()
    templates: tuple = ()

    @property
    def origin(self): return origin(self.url) if self.kind=='web' else 'local-desktop'

    @property
    def scope(self):
        # Separate states/personas by site/route IDs. Configuration changes never clear old incidents.
        return digest({'target':self.id,'url':self.url,'audit':self.audit,'expect':self.expect,'kind':self.kind,'region':self.region,'templates':self.templates,'masks':self.mask_rects})[:24]


@dataclass
class WatchConfig:
    project: str
    targets: list[Target]
    output: Path
    root: Path
    max_workers: int = 4
    per_origin: int = 1
    max_hot_pages: int = 2
    max_tier: int = 2
    poll_s: float = .5
    confirmation_scans: int = 2
    recovery_scans: int = 2
    repeat_gap_s: float = .15
    cpu_limit: float = 80
    reserve_mb: int = 768
    worker_mb: int = 384
    evidence_limit_mb: int = 4096
    disk_reserve_mb: int = 512
    keep_events: int = 20000
    watch_paths: list[str] = field(default_factory=list)
    debounce_s: float = 1
    max_debounce_s: float = 5
    llm: dict = field(default_factory=dict)
    cv: dict = field(default_factory=dict)
    css_provenance: bool = False


def load(path: Path, *, output: Path | None = None, project_root: Path | None = None) -> WatchConfig:
    path=path.resolve(); raw=yaml.safe_load(path.read_text('utf-8'))
    closed(raw, {'schema','project','output','sites','resources','alerts','watch','llm','cv','screens','diagnostics'},'watch')
    if raw.get('schema')!='testwins.watch/v1': raise ValueError('Expected testwins.watch/v1')
    if not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}',raw.get('project','')): raise ValueError('Invalid project id')
    root=(project_root or path.parent).resolve()
    cfg=WatchConfig(raw['project'],[],(output or root/raw.get('output','.testwins/live')).resolve(),root)
    limits={'max_workers':(1,64,True),'per_origin':(1,8,True),'max_hot_pages':(0,64,True),'max_tier':(0,3,True),
      'poll_s':(.1,30,False),'cpu_limit':(5,99,False),'reserve_mb':(64,1048576,True),'worker_mb':(64,16384,True),
      'evidence_limit_mb':(8,1048576,True),'disk_reserve_mb':(0,1048576,True)}
    resources=raw.get('resources',{});closed(resources,limits,'resources')
    for k,v in resources.items():setattr(cfg,k,number(v,*limits[k][:2],k,limits[k][2]))
    alerts=raw.get('alerts',{});closed(alerts,{'confirmation_scans','recovery_scans','keep_events','repeat_gap_s'},'alerts')
    for k,lo,hi,integer in [('confirmation_scans',2,10,True),('recovery_scans',2,10,True),('keep_events',100,1000000,True),('repeat_gap_s',.05,5,False)]:
        if k in alerts:setattr(cfg,k,number(alerts[k],lo,hi,k,integer))
    watch=raw.get('watch',{});closed(watch,{'paths','debounce_s','max_debounce_s'},'watch paths')
    cfg.watch_paths=watch.get('paths',[])
    if not isinstance(cfg.watch_paths,list) or not all(isinstance(x,str) for x in cfg.watch_paths):raise ValueError('watch.paths must be paths')
    for p in cfg.watch_paths:
        if not (root/p).resolve().is_relative_to(root):raise ValueError('Watch paths must stay in project root')
    cfg.debounce_s=number(watch.get('debounce_s',1),.1,60,'debounce_s')
    cfg.max_debounce_s=number(watch.get('max_debounce_s',5),cfg.debounce_s,120,'max_debounce_s')
    llm=raw.get('llm',{});closed(llm,{'enabled','env_file','calls_per_hour','max_inflight','cooldown_s'},'llm')
    if type(llm.get('enabled',False)) is not bool:raise ValueError('llm.enabled must be boolean')
    cfg.llm={'enabled':False,'env_file':'.env','calls_per_hour':4,'max_inflight':1,'cooldown_s':900,**llm}
    number(cfg.llm['calls_per_hour'],0,1000,'calls_per_hour',True)
    number(cfg.llm['max_inflight'],1,4,'max_inflight',True);number(cfg.llm['cooldown_s'],60,86400,'cooldown_s')
    cfg.cv={'enabled':False,'backend':'opencv','weights':None,'trust_model':False,**raw.get('cv',{})}
    closed(cfg.cv,{'enabled','backend','weights','trust_model'},'cv')
    if cfg.cv['backend'] not in {'opencv','yolo'}:raise ValueError('Only opencv/yolo supported for live CV')
    if any(type(cfg.cv[k]) is not bool for k in ('enabled','trust_model')):raise ValueError('Invalid CV flags')
    diagnostics=raw.get('diagnostics',{})
    closed(diagnostics,{'css_provenance'},'diagnostics')
    cfg.css_provenance=diagnostics.get('css_provenance',False)
    if type(cfg.css_provenance) is not bool:raise ValueError('css_provenance must be boolean')
    sites=raw.get('sites',[])
    if not isinstance(sites,list):raise ValueError('sites must be a list')
    seen_sites=set();seen=set()
    for site in sites:
        closed(site,{'id','base_url','pages','browsers','devices','interval_s','priority','hot','source_globs','audit_config'},'site')
        sid=site.get('id','')
        if not re.fullmatch(r'[a-z][a-z0-9_-]{0,47}',sid) or sid in seen_sites:raise ValueError('Invalid/duplicate site id')
        seen_sites.add(sid);base=site['base_url'];origin(base)
        if urlsplit(base).username or urlsplit(base).password:raise ValueError('Credentials in URL forbidden')
        audit=audit_load((root/site['audit_config']).resolve()) if site.get('audit_config') else audit_load()
        # Continuous scans have their own route inventory. No implicit execution of journeys.
        if not site.get('audit_config'):
            audit['axe']['enabled']=False;audit['axe']['required']=False
        if not site.get('audit_config'):audit['headless']=True
        audit['base_url']=base
        browsers=site.get('browsers',['chromium']);devices=site.get('devices',['desktop'])
        if not isinstance(browsers,list) or not browsers or any(b not in set(sum(MATRICES.values(),[])) for b in browsers):raise ValueError('Invalid browsers')
        if not isinstance(devices,list) or not devices or any(d not in audit['devices'] for d in devices):raise ValueError('Invalid devices')
        pages=site.get('pages',['/'])
        if not isinstance(pages,list) or not pages:raise ValueError('pages must be explicit nonempty list')
        for page in pages:
            p={'path':page} if isinstance(page,str) else page
            closed(p,{'id','path','interval_s','priority','hot','expect','source_globs'},'page')
            url=urljoin(base,p['path'])
            if origin(url)!=origin(base):raise ValueError('Page cannot leave site origin')
            # Do not put authentication tokens/query secrets in a replayable inventory.
            from ..util import redact_url
            if redact_url(url)!=url:raise ValueError('Sensitive query parameters are forbidden; use disposable test data')
            route=p.get('id','page-'+digest(p['path'])[:12])
            if not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}',route):raise ValueError('Invalid route id')
            interval=number(p.get('interval_s',site.get('interval_s',60)),1,86400,'interval_s')
            priority=number(p.get('priority',site.get('priority',2)),0,4,'priority',True)
            hot=p.get('hot',site.get('hot',False))
            if type(hot) is not bool:raise ValueError('hot must be boolean')
            expectations=p.get('expect',[])
            if not isinstance(expectations,list) or len(expectations)>50:raise ValueError('Invalid expectations')
            for e in expectations:
                closed(e,{'kind','selector','value','severity'},'expect')
                if e.get('severity','high') not in {'critical','high','normal','low'}:raise ValueError('Invalid expectation severity')
                if e.get('kind') not in {'visible','hidden','text','count'} or not isinstance(e.get('selector'),str):raise ValueError('Only read-only DOM expectations allowed live')
                if e['kind']=='count':number(e.get('value'),0,100000,'count',True)
                if e['kind']=='text' and not isinstance(e.get('value'),str):raise ValueError('text value required')
            globs=p.get('source_globs',site.get('source_globs',[]))
            if not isinstance(globs,list) or not all(isinstance(g,str) for g in globs):raise ValueError('Invalid source_globs')
            for b in browsers:
                for d in devices:
                    tid=f'{sid}:{route}:{b}:{d}'
                    if tid in seen:raise ValueError('Duplicate matrix cell')
                    seen.add(tid)
                    cfg.targets.append(Target(tid,sid,url,route,b,d,interval,priority,hot,tuple(expectations),tuple(globs),copy.deepcopy(audit)))
    screens=raw.get('screens',[])
    if not isinstance(screens,list):raise ValueError('screens must be a list')
    for screen in screens:
        closed(screen,{'id','region','interval_s','priority','mask_rects','allow_desktop_capture','templates'},'screen')
        sid=screen.get('id','')
        if not re.fullmatch(r'[a-z][a-z0-9_-]{0,47}',sid) or sid in seen_sites:raise ValueError('Invalid/duplicate screen id')
        seen_sites.add(sid)
        if screen.get('allow_desktop_capture') is not True:raise ValueError('Local screen capture requires explicit allow_desktop_capture:true')
        region=screen.get('region',{});closed(region,{'left','top','width','height'},'capture region')
        for k in ('left','top'):number(region.get(k),-32000,32000,k,True)
        for k in ('width','height'):number(region.get(k),100,4000,k,True)
        masks=screen.get('mask_rects',[])
        if not isinstance(masks,list):raise ValueError('mask_rects must be rectangles')
        for m in masks:
            closed(m,{'x','y','width','height'},'mask')
            for k in ('x','y','width','height'):number(m.get(k),0,4000,k,True)
            if m['x']+m['width']>region['width'] or m['y']+m['height']>region['height']:raise ValueError('Mask outside capture region')
        templates=screen.get('templates',[])
        if not isinstance(templates,list) or len(templates)>20:raise ValueError('Invalid templates')
        for template in templates:
            closed(template,{'path','present','threshold'},'template')
            if not isinstance(template.get('path'),str) or type(template.get('present',True)) is not bool:raise ValueError('Invalid template')
            number(template.get('threshold',.95),.5,1,'threshold')
            if not (root/template['path']).resolve().is_file():raise ValueError('Template must be an existing local image')
        cfg.targets.append(Target(id=f'{sid}:screen:native:region',site=sid,url='desktop://'+sid,route='screen',browser='native',device='region',
            interval_s=number(screen.get('interval_s',2),.25,86400,'interval_s'),priority=number(screen.get('priority',2),0,4,'priority',True),
            kind='desktop',region=region,mask_rects=tuple(masks),templates=tuple(templates)))
    if not cfg.targets:raise ValueError('At least one site or explicitly authorized screen is required')
    launch_specs={}
    for t in cfg.targets:
        if t.kind!='web':continue
        spec={k:t.audit[k] for k in ('executables','cdp_endpoints','headless','sandbox')}
        if t.browser in launch_specs and launch_specs[t.browser]!=spec:
            raise ValueError('One agent requires a single launch configuration per browser; shard incompatible configurations')
        launch_specs[t.browser]=spec
    if len(cfg.targets)>10000:raise ValueError('Single-agent inventory limit is 10000 cells; shard larger inventories')
    return cfg


def affected(target: Target, paths: list[str]) -> bool:
    return not target.source_globs or any(fnmatch.fnmatchcase(p,g) for p in paths for g in target.source_globs)
