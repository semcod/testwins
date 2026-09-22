from pathlib import Path
import json
from .events import verify as verify_events
from .util import confined, file_digest

def verify_run(root: Path) -> dict:
    manifest=json.loads((root/'manifest.json').read_text('utf-8'))
    if manifest.get('schema')!='testwins.report-manifest/v1' or manifest.get('authority')!='none':
        raise ValueError('Unsupported manifest or invalid authority')
    if file_digest(root/'report.json')!=manifest['report_sha256']:raise ValueError('Report digest mismatch')
    seen=set()
    for e in manifest['evidence']:
        if e['path'] in seen:raise ValueError('Duplicated evidence path')
        seen.add(e['path']);p=confined(root,e['path'])
        if not p.is_file() or p.stat().st_size!=e['bytes'] or file_digest(p)!=e['sha256']:
            raise ValueError('Evidence integrity failure: '+e['path'])
    result=verify_events(root)
    events=[json.loads(line) for line in (root/'logs/audit.jsonl').read_text('utf-8').splitlines()]
    if len(events)<2 or events[0]['eventType']!='testwins.run_started' or events[-1]['eventType']!='testwins.run_completed':
        raise ValueError('Missing run lifecycle boundary events')
    required={'report.json','manifest.json','proposals.json'}
    if not required<={e['path'] for e in events[-1]['evidence']}:raise ValueError('Missing final evidence anchors')
    return dict(result,files=len(seen),manifest='verified',authenticity='not signed; hashes detect modification, not a malicious full rewrite')
