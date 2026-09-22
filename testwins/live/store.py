from __future__ import annotations
import json
import sqlite3
import threading
import time
from pathlib import Path
from ..util import digest


class Store:
    """One agent, many readers. WAL is local-disk only; never share it over NFS."""
    def __init__(self,path: Path,confirm=2,recover=2,keep_events=20000):
        path.parent.mkdir(parents=True,exist_ok=True)
        self.path=path;self.confirm=confirm;self.recover=recover;self.keep_events=keep_events
        self.lock=threading.RLock()
        self.db=sqlite3.connect(path,timeout=10,check_same_thread=False)
        self.db.row_factory=sqlite3.Row
        self.db.executescript('''
        PRAGMA journal_mode=WAL;
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS incidents(
          id TEXT PRIMARY KEY,target TEXT NOT NULL,scope TEXT NOT NULL,rule TEXT NOT NULL,
          state TEXT NOT NULL,hits INTEGER NOT NULL,misses INTEGER NOT NULL,first REAL NOT NULL,last REAL NOT NULL,
          detail TEXT NOT NULL,evidence TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS incident_target ON incidents(target,scope,state);
        CREATE TABLE IF NOT EXISTS targets(id TEXT PRIMARY KEY,scope TEXT NOT NULL,last REAL NOT NULL,status TEXT NOT NULL,detail TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,ts REAL NOT NULL,kind TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS scans(id INTEGER PRIMARY KEY AUTOINCREMENT,target TEXT NOT NULL,ts REAL NOT NULL,duration REAL NOT NULL,complete INTEGER NOT NULL);
        CREATE INDEX IF NOT EXISTS scan_target ON scans(target,ts);
        CREATE TABLE IF NOT EXISTS calls(id INTEGER PRIMARY KEY AUTOINCREMENT,ts REAL NOT NULL,cache_key TEXT NOT NULL,target TEXT NOT NULL,state TEXT NOT NULL,detail TEXT);
        CREATE INDEX IF NOT EXISTS calls_time ON calls(ts);
        ''');self.db.commit()

    def close(self):
        with self.lock:self.db.close()

    def _emit(self,kind,payload,now):
        cur=self.db.execute('INSERT INTO events(ts,kind,payload) VALUES(?,?,?)',(now,kind,json.dumps(payload,ensure_ascii=False)))
        return {'id':cur.lastrowid,'ts':now,'kind':kind,'payload':payload}

    def emit(self,kind,payload,now=None):
        with self.lock,self.db:
            event=self._emit(kind,payload,time.time() if now is None else now)
            self.db.execute('DELETE FROM events WHERE id <= (SELECT COALESCE(MAX(id),0)-? FROM events)',(self.keep_events,))
            return event

    def record(self,target,scope,result,now=None):
        now=time.time() if now is None else now;emitted=[]
        covered=set(result.get('covered_rules',[]));seen=set()
        with self.lock,self.db:
            previous=self.db.execute('SELECT scope,status,detail FROM targets WHERE id=?',(target,)).fetchone()
            self.db.execute('INSERT OR REPLACE INTO targets VALUES(?,?,?,?,?)',
                (target,scope,now,result['status'],json.dumps(result,ensure_ascii=False)))
            self.db.execute('INSERT INTO scans(target,ts,duration,complete) VALUES(?,?,?,?)',
                (target,now,result.get('duration_s',0),int(result['status']=='complete')))
            self.db.execute('DELETE FROM scans WHERE target=? AND id NOT IN (SELECT id FROM scans WHERE target=? ORDER BY id DESC LIMIT 64)',(target,target))
            if previous and previous['scope']!=scope:
                emitted.append(self._emit('scope_changed',{'target':target,'old_scope':previous['scope'],'scope':scope,'old_incidents_not_auto_resolved':True},now))
            for f in result.get('findings',[]):
                key=digest({'target':target,'scope':scope,'rule':f['rule'],'selectors':sorted(set(f.get('selectors',[]))),'contract':f.get('details',{}).get('contract_id')})[:40]
                if key in seen:continue
                seen.add(key)
                row=self.db.execute('SELECT * FROM incidents WHERE id=?',(key,)).fetchone()
                eligible=not f.get('candidate',False) and f['rule'] in covered
                hits=(row['hits']+1 if row and row['state']!='resolved' and row['misses']==0 else 1) if eligible else 0
                state=('confirmed' if hits>=self.confirm else 'observed') if eligible else 'candidate'
                # A newly uncertain capture does not revoke previously confirmed evidence.
                if row and row['state']=='confirmed':state='confirmed'
                first=row['first'] if row else now
                evidence=result.get('evidence','')
                if row and row['state']=='confirmed' and not eligible:
                    f=json.loads(row['detail']);evidence=row['evidence']
                self.db.execute('INSERT OR REPLACE INTO incidents VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                    (key,target,scope,f['rule'],state,hits,0,first,now,json.dumps(f,ensure_ascii=False),evidence))
                kind='incident_opened' if not row else 'incident_reopened' if row['state']=='resolved' else 'incident_confirmed' if state=='confirmed' and row['state']!='confirmed' else None
                if kind:emitted.append(self._emit(kind,{'id':key,'target':target,'scope':scope,'state':state,'finding':f,'evidence':evidence},now))
            rows=self.db.execute("SELECT * FROM incidents WHERE target=? AND scope=? AND state!='resolved'",(target,scope)).fetchall()
            for row in rows:
                if row['id'] in seen:continue
                if row['rule'] not in covered:
                    # A coverage gap is neither a clean measurement nor an additional
                    # consecutive hit. Preserve the incident, but break both streaks.
                    self.db.execute('UPDATE incidents SET hits=0,misses=0 WHERE id=?',(row['id'],))
                    continue
                misses=row['misses']+1;state='resolved' if misses>=self.recover else row['state']
                self.db.execute('UPDATE incidents SET misses=?,hits=0,state=?,last=? WHERE id=?',(misses,state,now,row['id']))
                if state=='resolved':emitted.append(self._emit('incident_resolved',{'id':row['id'],'target':target,'scope':scope,'rule':row['rule'],'clean_scans':misses,'meaning':'rule absent in repeated comparable covered scans'},now))
            # One coverage transition, not thousands of identical alerts on every scan.
            if not previous or previous['status']!=result['status'] or json.loads(previous['detail']).get('gaps',[])!=result.get('gaps',[]):
                emitted.append(self._emit('coverage_changed',{'target':target,'status':result['status'],'gaps':result.get('gaps',[])},now))
            self.db.execute('DELETE FROM events WHERE id <= (SELECT COALESCE(MAX(id),0)-? FROM events)',(self.keep_events,))
        return emitted

    def events(self,after=0,limit=200):
        with self.lock:
            return [{'id':r['id'],'ts':r['ts'],'kind':r['kind'],'payload':json.loads(r['payload'])}
                    for r in self.db.execute('SELECT * FROM events WHERE id>? ORDER BY id LIMIT ?',(after,min(1000,limit)))]

    def event_bounds(self):
        with self.lock:
            r=self.db.execute('SELECT MIN(id),MAX(id) FROM events').fetchone();return r[0] or 0,r[1] or 0

    def status(self,all_incidents=False,compact=False,display_limit=5000):
        display_limit=max(1,min(5000,int(display_limit)))
        with self.lock:
            targets=[{'id':r['id'],'scope':r['scope'],'last':r['last'],'status':r['status'],**json.loads(r['detail'])}
                     for r in self.db.execute('SELECT * FROM targets ORDER BY id')]
            incidents=[{**dict(r),'detail':json.loads(r['detail'])} for r in self.db.execute("SELECT * FROM incidents WHERE state!='resolved' ORDER BY last DESC"+("" if all_incidents else " LIMIT "+str(display_limit)))]
            if compact:
                for target in targets:
                    target['finding_count']=len(target.pop('findings',[]))
            totals={r[0]:r[1] for r in self.db.execute('SELECT state,COUNT(*) FROM incidents GROUP BY state')}
            return {'schema':'testwins.live-status/v1','generated_at':time.time(),'targets':targets,'incidents':incidents,'totals':totals,'incident_display_limit':None if all_incidents else display_limit,'incidents_truncated':sum(v for k,v in totals.items() if k!='resolved')>len(incidents),'last_event':self.event_bounds()[1]}

    def protected_evidence(self):
        with self.lock:
            paths={r[0] for r in self.db.execute("SELECT evidence FROM incidents WHERE state!='resolved'") if r[0]}
            for r in self.db.execute('SELECT detail FROM targets'):
                e=json.loads(r[0]).get('evidence')
                if e:paths.add(e)
            return paths

    def reserve_call(self,key,target,limit,cooldown,max_inflight=1,now=None):
        now=time.time() if now is None else now
        with self.lock,self.db:
            # Failed requests still consume quota. Restart does not reset the ledger.
            self.db.execute("UPDATE calls SET state='abandoned' WHERE state='reserved' AND ts<?",(now-300,))
            if self.db.execute('SELECT COUNT(*) FROM calls WHERE ts>?',(now-3600,)).fetchone()[0]>=limit:return None,'hourly_budget'
            if self.db.execute("SELECT COUNT(*) FROM calls WHERE state='reserved'").fetchone()[0]>=max_inflight:return None,'inflight_limit'
            if self.db.execute('SELECT 1 FROM calls WHERE target=? AND ts>?',(target,now-cooldown)).fetchone():return None,'cooldown'
            if self.db.execute('SELECT 1 FROM calls WHERE cache_key=? AND ts>?',(key,now-86400)).fetchone():return None,'cached_or_recently_attempted'
            cur=self.db.execute('INSERT INTO calls(ts,cache_key,target,state) VALUES(?,?,?,?)',(now,key,target,'reserved'))
            return cur.lastrowid,'reserved'

    def finish_call(self,call_id,state,detail):
        with self.lock,self.db:self.db.execute('UPDATE calls SET state=?,detail=? WHERE id=?',(state,json.dumps(detail,ensure_ascii=False),call_id))

    def latency_anomaly(self,target,current,ratio=3):
        """Robust median/MAD screen; observer duration, not a frontend performance verdict."""
        from statistics import median
        with self.lock:xs=[r[0] for r in self.db.execute('SELECT duration FROM scans WHERE target=? AND complete=1 ORDER BY id DESC LIMIT 31',(target,))]
        if len(xs)<8:return None
        center=median(xs);mad=median(abs(x-center) for x in xs)
        if current>max(center*ratio,center+6*1.4826*mad,center+1):
            return {'duration_s':current,'baseline_median_s':center,'mad_s':mad,'kind':'observer_latency_anomaly','root_cause':'unknown; may be SUT, browser or scanning host load'}
        return None
