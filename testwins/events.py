"""Restricted wellmanifest.logs/event/v1 emitter. No raw output or model text in events.
Contract reference: wellmanifest/logs contracts/logs.contract.v0.5.json (observed 2026-09-22).
Full upstream validation is deliberately a separate, explicit conformance command.
"""
from __future__ import annotations
import hashlib
import json
import re
import uuid
from pathlib import Path
from .util import canonical, file_digest, confined, utc_now

ZERO = "0"*64
FIELDS = set("schema eventId stream sequence eventType severity mode occurredAt correlationId causationId producer source code subjectRef outcome subjectState evidence inputHash receiptRef previousHash eventHash rawOutputIncluded secretMaterialIncluded".split())


class EventLog:
    def __init__(self, root: Path, correlation: str):
        self.root=root; self.correlation=correlation
        self.path=root/"logs"/"audit.jsonl"; self.path.parent.mkdir(parents=True,exist_ok=True)
        if self.path.exists(): raise ValueError("A run log is immutable; use a new run directory")
        self.sequence=0;self.previous=ZERO;self.last=None

    def append(self, kind: str, *, input_hash: str, evidence: list[str] | None = None,
               code: str | None = None, severity: str = "INFO", outcome: str = "OBSERVED",
               state: str | None = None) -> dict:
        if not re.fullmatch(r"[a-f0-9]{64}",input_hash):raise ValueError("invalid input hash")
        ev=[]
        for rel in (evidence or [])[:16]:
            p=confined(self.root,rel)
            ev.append({"path":rel,"sha256":file_digest(p)})
        self.sequence+=1
        event={"schema":"wellmanifest.logs/event/v1","eventId":"event:"+uuid.uuid4().hex,
               "stream":"audit","sequence":self.sequence,"eventType":"testwins."+kind,
               "severity":severity,"mode":"APPLY","occurredAt":utc_now(),
               "correlationId":self.correlation,"causationId":self.last,
               "producer":"service:testwins","source":"testwins.audit","code":code,
               "subjectRef":"testwins:run/"+self.correlation,"outcome":outcome,"subjectState":state,
               "evidence":ev,"inputHash":input_hash,"receiptRef":None,
               "previousHash":self.previous,"rawOutputIncluded":False,"secretMaterialIncluded":False}
        event["eventHash"]=hashlib.sha256(canonical(event,integers_only=True)).hexdigest()
        with self.path.open("ab") as f:
            f.write(canonical(event,integers_only=True)+b"\n");f.flush()
            import os
            os.fsync(f.fileno())
        self.previous=event["eventHash"];self.last=event["eventId"]
        return event


def verify(root: Path) -> dict:
    previous=ZERO;seen=set();count=0
    for count,line in enumerate((root/"logs/audit.jsonl").read_bytes().splitlines(),1):
        e=json.loads(line)
        if set(e)!=FIELDS:raise ValueError("closed event fields mismatch")
        if line!=canonical(e,integers_only=True):raise ValueError("non-canonical event")
        if e["schema"]!="wellmanifest.logs/event/v1" or e["stream"]!="audit":raise ValueError("event identity mismatch")
        if e["sequence"]!=count or e["previousHash"]!=previous:raise ValueError("event chain mismatch")
        if e["eventId"] in seen:raise ValueError("duplicate event id")
        if e["causationId"] is not None and e["causationId"] not in seen:raise ValueError("unknown cause")
        seen.add(e["eventId"])
        if e["rawOutputIncluded"] is not False or e["secretMaterialIncluded"] is not False:raise ValueError("unsafe flags")
        if e["severity"] not in ("DEBUG","INFO","WARNING","ERROR","CRITICAL"):raise ValueError("severity mismatch")
        actual=hashlib.sha256(canonical({k:v for k,v in e.items() if k!="eventHash"},integers_only=True)).hexdigest()
        if actual!=e["eventHash"]:raise ValueError("event hash mismatch")
        for ev in e["evidence"]:
            if file_digest(confined(root,ev["path"]))!=ev["sha256"]:raise ValueError("evidence digest mismatch")
        previous=actual
    return {"valid":True,"events":count,"head":previous,"scope":"local restricted-profile and evidence validation"}
