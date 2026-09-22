from __future__ import annotations
import math
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

@dataclass
class Resources:
    cpu_percent: float
    available_mb: float
    cpu_count: float
    disk_free_mb: float
    source: str='host'


def sample(path: Path) -> Resources:
    import psutil
    memory=psutil.virtual_memory().available/1048576
    cpu=float(psutil.cpu_percent(interval=None));cores=float(os.cpu_count() or 1);source='host'
    try:cores=min(cores,len(os.sched_getaffinity(0)))
    except (OSError,AttributeError):pass
    c=Path('/sys/fs/cgroup')
    try:
        limit=(c/'memory.max').read_text().strip()
        if limit!='max':memory=min(memory,max(0,int(limit)-int((c/'memory.current').read_text()))/1048576);source='host+cgroup-v2'
    except (OSError,ValueError):pass
    try:
        quota,period=(c/'cpu.max').read_text().split()
        if quota!='max':cores=min(cores,int(quota)/int(period));source='host+cgroup-v2'
    except (OSError,ValueError,ZeroDivisionError):pass
    path.mkdir(parents=True,exist_ok=True)
    return Resources(cpu,memory,max(.1,cores),shutil.disk_usage(path).free/1048576,source)


class Governor:
    def __init__(self,cfg):self.cfg=cfg;self.penalty=0;self.healthy=0
    def decide(self,r: Resources):
        c=self.cfg;reasons=[]
        if r.cpu_percent>=c.cpu_limit:
            self.penalty=min(c.max_workers,self.penalty+1);self.healthy=0;reasons.append('cpu_pressure')
        elif r.cpu_percent<c.cpu_limit-15:
            self.healthy+=1
            if self.healthy>=3:self.penalty=max(0,self.penalty-1);self.healthy=0
        memory=max(0,int((r.available_mb-c.reserve_mb)//c.worker_mb))
        workers=min(c.max_workers,max(1,math.ceil(r.cpu_count)),memory)
        workers=max(0,workers-self.penalty)
        tier=c.max_tier
        if r.available_mb<c.reserve_mb+c.worker_mb:reasons.append('memory_pressure');workers=0
        if r.disk_free_mb<c.disk_reserve_mb:reasons.append('disk_pressure');workers=0
        if self.penalty:tier=min(tier,1)
        if r.available_mb<c.reserve_mb+2*c.worker_mb:tier=min(tier,1)
        return {'workers':workers,'tier':tier,'reasons':reasons,'resources':r.__dict__,
                'limits_are':'admission-control, not OS-enforced process memory limits'}


def capacity(cells:int,seconds:float,workers:int,interval:float):
    cycle=math.inf if workers<=0 else cells*seconds/workers
    return {'cells':cells,'assumed_seconds_per_cell':seconds,'workers':workers,'requested_interval_s':interval,
            'ideal_cycle_s':None if not math.isfinite(cycle) else cycle,'feasible_at_ideal_utilization':cycle<=interval,
            'utilization':None if not math.isfinite(cycle) else cycle/interval,
            'model':'N*t/C; excludes startup, origin limits, tail latency, retries and LLM; not a benchmark'}
