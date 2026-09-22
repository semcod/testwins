from __future__ import annotations
import asyncio
import fnmatch
import json
import os
import shutil
import time
from pathlib import Path
from .config import affected
from .policy import Governor,sample
from .store import Store
from ..util import atomic_json


class Lease:
    """Prevent two writers using one agent directory. POSIX and Windows file locks."""
    def __init__(self,path):self.path=path;self.f=None
    def __enter__(self):
        self.path.parent.mkdir(parents=True,exist_ok=True);self.f=self.path.open('a+b');self.f.write(b'0');self.f.flush();self.f.seek(0)
        try:
            if os.name=='nt':
                import msvcrt;msvcrt.locking(self.f.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl;fcntl.flock(self.f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.f.close();raise RuntimeError('Another Testwins monitor owns this output directory') from None
        return self
    def __exit__(self,*_):
        if self.f:self.f.close()


class Changes:
    """Bounded mtime watcher. Does not read source contents or claim source causality."""
    SKIP={'.git','.venv','venv','node_modules','dist','build','__pycache__','.testwins','.wup','.planfile','artifacts','verification'}
    def __init__(self,cfg):self.cfg=cfg;self.previous=None;self.truncated=False
    def poll(self):
        current={};self.truncated=False
        for relative in self.cfg.watch_paths:
            base=(self.cfg.root/relative).resolve()
            if not base.exists():continue
            entries=[base] if base.is_file() else None
            if entries is None:
                def paths():
                    for root,dirs,files in os.walk(base,followlinks=False):
                        dirs[:]=sorted(d for d in dirs if d not in self.SKIP and not (Path(root)/d).is_symlink() and not (Path(root)/d).resolve().is_relative_to(self.cfg.output))
                        for f in sorted(files):yield Path(root)/f
                entries=paths()
            for path in entries:
                if path.is_symlink() or path.name.startswith('.env') or path.resolve().is_relative_to(self.cfg.output):continue
                try:
                    stat=path.stat();current[str(path.relative_to(self.cfg.root))]=(stat.st_mtime_ns,stat.st_size)
                except (ValueError,OSError):continue
                if len(current)>=20000:self.truncated=True;break
            if self.truncated:break
        changes=[] if self.previous is None else sorted(k for k in set(current)|set(self.previous) if current.get(k)!=self.previous.get(k))
        self.previous=current;return changes


class Retention:
    def __init__(self,cfg,store):self.cfg=cfg;self.store=store;self.last=0;self.last_total=0
    def maintain(self,force=False,extra_protected=()):
        if not force and time.monotonic()-self.last<15:return self.last_total<self.cfg.evidence_limit_mb*1048576
        self.last=time.monotonic();root=self.cfg.output/'evidence';root.mkdir(parents=True,exist_ok=True)
        reviews=self.cfg.output/'augmentations';reviews.mkdir(parents=True,exist_ok=True)
        protected=self.store.protected_evidence()|set(extra_protected);items=[];total=0
        for p in [*root.iterdir(),*reviews.iterdir()]:
            if p.is_symlink() or not p.is_dir():continue
            try:
                size=sum(f.stat().st_size for f in p.rglob('*') if f.is_file() and not f.is_symlink());total+=size
                items.append((p.stat().st_mtime,p,size))
            except OSError:continue
        limit=self.cfg.evidence_limit_mb*1048576
        for mtime,p,size in sorted(items):
            if total<limit*.85:break
            if str(p.relative_to(self.cfg.output)) in protected:continue
            shutil.rmtree(p);total-=size
        self.last_total=total
        # Old resolved metadata is bounded; never silently discard active incidents.
        with self.store.lock,self.store.db:
            self.store.db.execute("DELETE FROM incidents WHERE state='resolved' AND last<?",(time.time()-30*86400,))
            self.store.db.execute('DELETE FROM calls WHERE ts<?',(time.time()-7*86400,))
        return total<limit


class Monitor:
    def __init__(self,cfg,scanner,store,*,resource_sampler=sample,printer=None,augmenter=None):
        self.cfg=cfg;self.scanner=scanner;self.store=store;self.sample=resource_sampler;self.printer=printer
        self.governor=Governor(cfg);self.augmenter=augmenter;self.stop=asyncio.Event()
        self.targets={t.id:t for t in cfg.targets};self.due={t.id:time.monotonic() for t in cfg.targets}
        self.reason={t.id:'initial' for t in cfg.targets};self.pending={};self.generation={t.id:0 for t in cfg.targets}
        self.attempt_status={};self.active={};self.active_origin={};self.origin_next={};self.done=set();self.scans=0;self.last_policy=None
        self.changes=Changes(cfg);self.retention=Retention(cfg,store);self.next_fs=0;self.last_tick=time.monotonic()
    def request(self,target_ids=None,reason='source'):
        now=time.monotonic()
        for tid in (target_ids if target_ids is not None else self.targets):
            if tid not in self.targets:continue
            first,_,old=self.pending.get(tid,(now,now,reason))
            self.pending[tid]=(first,now,'source' if 'source' in (old,reason) else reason)
            self.generation[tid]+=1
    def flush(self):
        now=time.monotonic()
        for tid,(first,last,reason) in list(self.pending.items()):
            if now-last>=self.cfg.debounce_s or now-first>=self.cfg.max_debounce_s:
                self.due[tid]=min(self.due[tid],now);self.reason[tid]=reason;self.pending.pop(tid,None)
    def event(self,kind,payload):
        e=self.store.emit(kind,payload)
        if self.printer:self.printer(e)
    async def _execute(self,t,tier,reason,version):
        try:
            try:
                result=await asyncio.wait_for(self.scanner.scan(t,tier,reason),timeout=t.audit.get('capture',{}).get('max_cell_seconds',60))
            except Exception as exc:
                result={'status':'incomplete','findings':[],'covered_rules':[],'gaps':[{'kind':'worker_failed','exception_type':type(exc).__name__}],
                        'duration_s':0,'evidence':'','tier':tier}
            latency=self.store.latency_anomaly(t.id,result.get('duration_s',0))
            if latency:self.event('observer_latency_anomaly',{'target':t.id,**latency})
            for e in self.store.record(t.id,t.scope,result):
                if self.printer:self.printer(e)
            if self.augmenter and result.get('evidence') and result.get('findings') and tier>=2:
                self.augmenter.submit(t,result,tier)
            self.attempt_status[t.id]=result['status']
            self.scans+=1;self.done.add(t.id)
        except asyncio.CancelledError:raise
        except Exception as exc:
            self.attempt_status[t.id]='incomplete'
            self.event('monitor_error',{'target':t.id,'exception_type':type(exc).__name__})
            self.done.add(t.id)
        finally:
            self.due[t.id]=time.monotonic()+(t.interval_s if version==self.generation[t.id] else self.cfg.debounce_s)
            if version==self.generation[t.id]:self.reason[t.id]='periodic'
            self.active_origin[t.origin]=max(0,self.active_origin.get(t.origin,1)-1)
    async def run(self,*,once=False,max_scans=None):
        self.cfg.output.mkdir(parents=True,exist_ok=True);started=time.monotonic();paused_since=None;last_stats=0
        self.event('monitor_started',{'cells':len(self.targets),'mode':'once' if once else 'continuous','max_workers':self.cfg.max_workers})
        try:
            await self.scanner.start()
            if self.augmenter:await self.augmenter.start()
            while not self.stop.is_set():
                now=time.monotonic()
                for tid,task in list(self.active.items()):
                    if task.done():
                        try:task.result()
                        except asyncio.CancelledError:pass
                        self.active.pop(tid,None)
                if once and len(self.done)==len(self.targets) and not self.active:break
                if max_scans is not None and self.scans>=max_scans:break
                if now>=self.next_fs:
                    changed=await asyncio.to_thread(self.changes.poll);self.next_fs=now+max(1,self.cfg.debounce_s)
                    if changed:self.request([t.id for t in self.targets.values() if affected(t,changed)],'source')
                    if self.changes.truncated and not getattr(self,'_watch_warned',False):
                        self.event('coverage_gap',{'kind':'watch_file_limit','limit':20000});self._watch_warned=True
                if not once:
                    for tid in await self.scanner.dirty():self.request([tid],'dom')
                self.flush()
                if self.last_policy is None or now-self.last_tick>=1:
                    self.last_tick=now;self.last_policy=self.governor.decide(self.sample(self.cfg.output))
                decision=self.last_policy
                # Bound growth even under a permanently non-empty queue. Every 15 s stop
                # admitting captures, drain the bounded batch, then prune only immutable
                # bundles. Model jobs pin queued sources and in-flight destinations.
                maintenance_wait=bool(self.active) and now-self.retention.last>=15
                protected=self.augmenter.protected_evidence() if self.augmenter else ()
                storage_ok=(self.retention.last_total<self.cfg.evidence_limit_mb*1048576) if self.active else await asyncio.to_thread(self.retention.maintain,extra_protected=protected)
                if self.augmenter:self.augmenter.storage_paused=not storage_ok
                workers=decision['workers'] if storage_ok and not maintenance_wait else 0
                if workers==0 and not maintenance_wait:
                    if paused_since is None:
                        paused_since=now;self.event('resource_paused',{'decision':decision,'evidence_quota_ok':storage_ok})
                    if once and now-paused_since>30:
                        self.event('coverage_gap',{'kind':'admission_timeout','unscanned':[x for x in self.targets if x not in self.done]});break
                elif workers>0 and paused_since is not None:
                    self.event('resource_resumed',{'decision':decision});paused_since=None
                ready=[tid for tid in self.targets if self.due[tid]<=now and tid not in self.active and (not once or tid not in self.done)]
                # Earliest deadline with a bounded priority advantage; overdue low-priority cells age naturally.
                ready.sort(key=lambda tid:(self.due[tid]-min(5,self.targets[tid].interval_s*.05)*(4-self.targets[tid].priority),tid))
                for tid in ready:
                    if len(self.active)>=workers:break
                    if max_scans is not None and self.scans+len(self.active)>=max_scans:break
                    t=self.targets[tid]
                    if self.active_origin.get(t.origin,0)>=self.cfg.per_origin or now<self.origin_next.get(t.origin,0):continue
                    self.active_origin[t.origin]=self.active_origin.get(t.origin,0)+1;self.origin_next[t.origin]=now+.25
                    self.active[tid]=asyncio.create_task(self._execute(t,decision['tier'],self.reason[tid],self.generation[tid]))
                if now-last_stats>=5:
                    last_stats=now
                    stats={'cells':len(self.targets),'scans':self.scans,'inflight':len(self.active),'overdue':len(ready),
                           'max_lag_s':max([0]+[now-self.due[tid] for tid in ready]),'decision':decision,'maintenance_wait':maintenance_wait,'evidence_bytes':self.retention.last_total,'elapsed_s':now-started}
                    atomic_json(self.cfg.output/'health.json',stats)
                    self.event('heartbeat',stats)
                try:await asyncio.wait_for(self.stop.wait(),self.cfg.poll_s)
                except TimeoutError:pass
        finally:
            for job in self.active.values():job.cancel()
            await asyncio.gather(*self.active.values(),return_exceptions=True)
            if self.augmenter:await self.augmenter.close()
            await self.scanner.close()
            atomic_json(self.cfg.output/'status.json',self.store.status())
            self.event('monitor_stopped',{'scans':self.scans,'observed_cells':len(self.done),'configured_cells':len(self.targets)})
