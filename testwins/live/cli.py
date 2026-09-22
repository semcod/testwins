from __future__ import annotations
import argparse
import asyncio
import json
import signal
from pathlib import Path


def register(sub):
    w=sub.add_parser('watch',help='Continuous bounded GUI scans with persistent alerts')
    w.add_argument('--config',type=Path,default=Path('testwins.watch.yaml'));w.add_argument('--root',type=Path)
    w.add_argument('--output',type=Path);w.add_argument('--once',action='store_true');w.add_argument('--max-scans',type=int)
    w.add_argument('--serve',action='store_true');w.add_argument('--port',type=int,default=9067)
    w.add_argument('--host',default='127.0.0.1');w.add_argument('--allow-expose',action='store_true');w.add_argument('--quiet',action='store_true')
    s=sub.add_parser('live-status');s.add_argument('directory',type=Path)
    s=sub.add_parser('live-serve');s.add_argument('directory',type=Path);s.add_argument('--port',type=int,default=9067)
    s=sub.add_parser('live-export');s.add_argument('directory',type=Path);s.add_argument('--output',type=Path,required=True);s.add_argument('--project',required=True);s.add_argument('--include-candidates',action='store_true')
    c=sub.add_parser('capacity');c.add_argument('--config',type=Path,required=True);c.add_argument('--seconds-per-cell',type=float,default=2);c.add_argument('--workers',type=int);c.add_argument('--interval',type=float,default=60)
    d=sub.add_parser('diagnose');d.add_argument('snapshot',type=Path);d.add_argument('--output',type=Path,required=True)
    sub.add_parser('catalog',help='Machine-readable GUI failure taxonomy and coverage classification')


def run_watch(config,*,root=None,output=None,once=False,serve=False,port=9067,host='127.0.0.1',allow_expose=False,quiet=False,max_scans=None):
    from .config import load
    from .store import Store
    from .runtime import Monitor,Lease
    from .native import CompositeScanner
    from .augmentation import Augmenter
    from .server import Server
    cfg=load(config,output=output,project_root=root)
    if max_scans is not None and max_scans<1:raise ValueError('--max-scans must be positive')
    def printer(event):
        print(json.dumps(event,ensure_ascii=False),flush=True)
    with Lease(cfg.output/'agent.lock'):
        store=Store(cfg.output/'live.sqlite',cfg.confirmation_scans,cfg.recovery_scans,cfg.keep_events)
        server=None
        try:
            if serve:
                server=Server(store,host,port,allow_expose=allow_expose);server.start()
                if not quiet:print(json.dumps({'dashboard':f'http://{host}:{server.port}/'}),flush=True)
            monitor=Monitor(cfg,CompositeScanner(cfg),store,printer=None if quiet else printer,augmenter=Augmenter(cfg,store))
            async def run():
                loop=asyncio.get_running_loop()
                for sig in (signal.SIGINT,signal.SIGTERM):
                    try:loop.add_signal_handler(sig,monitor.stop.set)
                    except (NotImplementedError,ValueError):pass
                await monitor.run(once=once,max_scans=max_scans)
            try:asyncio.run(run())
            except KeyboardInterrupt:pass
            state=store.status()
            # Continuous daemon exit is a shutdown status. --once is a CI verdict for its declared scope only.
            if not once:return 0
            ids={t.id for t in cfg.targets}
            observed={t['id'] for t in state['targets'] if t['id'] in ids}
            if set(monitor.attempt_status)!=ids or any(status!='complete' for status in monitor.attempt_status.values()):return 2
            if monitor.done!=ids or observed!=ids or any(t['status'] not in {'complete'} for t in state['targets'] if t['id'] in ids):return 2
            if any(not f.get('candidate',False) for t in state['targets'] if t['id'] in ids for f in t.get('findings',[])):return 1
            return 0
        finally:
            if server:server.close()
            store.close()


def dispatch(a):
    from .store import Store
    if a.command=='watch':return run_watch(a.config,root=a.root,output=a.output,once=a.once,serve=a.serve,port=a.port,host=a.host,allow_expose=a.allow_expose,quiet=a.quiet,max_scans=a.max_scans)
    if a.command=='catalog':
        from .diagnosis import CATALOG
        print(json.dumps(CATALOG,ensure_ascii=False,indent=2));return 0
    if a.command=='diagnose':
        from .diagnosis import explain_file
        explain_file(a.snapshot,a.output);print(str(a.output));return 0
    if a.command=='capacity':
        from .config import load,number
        from .policy import capacity
        cfg=load(a.config);number(a.seconds_per_cell,.001,3600,'seconds-per-cell');number(a.interval,1,86400,'interval')
        workers=a.workers if a.workers is not None else cfg.max_workers;number(workers,1,64,'workers',True)
        print(json.dumps(capacity(len(cfg.targets),a.seconds_per_cell,workers,a.interval),ensure_ascii=False,indent=2));return 0
    if not (a.directory/'live.sqlite').is_file():raise ValueError('No live.sqlite in this directory')
    store=Store(a.directory/'live.sqlite')
    try:
        if a.command=='live-status':print(json.dumps(store.status(),ensure_ascii=False,indent=2))
        elif a.command=='live-export':
            from .export import export
            print(json.dumps(export(store,a.directory,a.output,a.project,a.include_candidates),ensure_ascii=False,indent=2))
        elif a.command=='live-serve':
            from .server import Server
            import time
            s=Server(store,port=a.port);s.start()
            try:
                while True:time.sleep(1)
            except KeyboardInterrupt:pass
            finally:s.close()
        return 0
    finally:store.close()
