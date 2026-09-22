#!/usr/bin/env python3
"""Scheduler/SQLite load test with FAKE captures. NOT a website/browser performance benchmark."""
from __future__ import annotations
import argparse
import asyncio
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from testwins.live.config import WatchConfig,Target
from testwins.live.runtime import Monitor
from testwins.live.store import Store
from testwins.live.policy import Resources
from testwins.util import atomic_json

class Synthetic:
    def __init__(self):self.active=0;self.maximum=0;self.seen=[]
    async def start(self):pass
    async def close(self):pass
    async def dirty(self):return []
    async def scan(self,t,tier,reason):
        self.active+=1;self.maximum=max(self.active,self.maximum);started=time.perf_counter()
        try:
            await asyncio.sleep(.01);self.seen.append(t.id)
            return {'status':'complete','findings':[],'covered_rules':[],'gaps':[], 'duration_s':time.perf_counter()-started,
                    'tier':tier,'evidence':'','synthetic':True}
        finally:self.active-=1

async def run(out:Path,n:int,workers:int):
    if out.exists():raise ValueError('Choose a new output directory')
    out.mkdir(parents=True);targets=[Target(f's{i}:home:chromium:desktop',f's{i}',f'http://synthetic-{i}.invalid/','home') for i in range(n)]
    cfg=WatchConfig('scheduler-only',targets,out/'data',out,max_workers=workers,poll_s=.001)
    store=Store(cfg.output/'live.sqlite');scanner=Synthetic();start=time.perf_counter()
    try:
        m=Monitor(cfg,scanner,store,resource_sampler=lambda _:Resources(1,65536,32,100000))
        await m.run(once=True)
        result={'kind':'synthetic scheduler and real SQLite; no web pages or browsers', 'cells':n,'unique_processed':len(set(scanner.seen)),
                'limit_workers':workers,'observed_maximum_concurrent':scanner.maximum,'wall_seconds':time.perf_counter()-start,
                'synthetic_delay_s':.01,'origins':'one artificial origin per cell; not a portal-origin throughput test',
                'resource_sampler':'fixed controlled values, not actual host pressure','browser_throughput_claim':False}
        assert result['unique_processed']==n;assert scanner.maximum<=workers
        atomic_json(out/'summary.json',result);print(json.dumps(result,indent=2))
    finally:store.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--cells',type=int,default=300);p.add_argument('--workers',type=int,default=6)
    a=p.parse_args()
    if not 1<=a.cells<=10000 or not 1<=a.workers<=64:p.error('Bounded range: cells 1..10000, workers 1..64')
    asyncio.run(run(a.output.resolve(),a.cells,a.workers))
