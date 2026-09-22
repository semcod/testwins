from __future__ import annotations
import json
import shutil
from collections import defaultdict
from pathlib import Path
from ..util import digest,atomic_json,file_digest,confined
from ..proposals import validate_producer
from .. import __version__


def export(store,root:Path,output:Path,project:str,include_candidates=False):
    output=output.resolve();root=root.resolve()
    if output==root or output.is_relative_to(root):raise ValueError('Export must be outside the live output directory')
    if output.exists():raise ValueError('Choose a new export directory')
    # Read one consistent view; copied immutable evidence is validated below.
    state=store.status(all_incidents=True);groups=defaultdict(list);scopes={t['id']:t['scope'] for t in state['targets']}
    for incident in state['incidents']:
        if scopes.get(incident['target'])!=incident['scope']:continue
        if incident['state']!='confirmed' and not include_candidates:continue
        parts=incident['target'].split(':');f=incident['detail']
        key=digest({'project':project,'site':parts[0],'route':parts[1],'rule':f['rule'],'selectors':sorted(f['selectors']),'contract':f.get('details',{}).get('contract_id')})[:40]
        groups[key].append(incident)
    output.mkdir(parents=True,exist_ok=False)
    atomic_json(output/'live-status.json',state);artifact_hash=file_digest(output/'live-status.json');proposals=[]
    for key,rows in groups.items():
        rows.sort(key=lambda r:({'critical':0,'high':1,'normal':2,'low':3}.get(r['detail']['severity'],3),r['target']))
        f=rows[0]['detail'];confirmed=any(r['state']=='confirmed' for r in rows);refs=[]
        for r in rows:
            rel=r['evidence']
            if not rel:continue
            src=confined(root,rel);dst=output/rel
            if not src.is_dir():raise ValueError('Evidence expired or unavailable; capture again before exporting')
            manifest=json.loads((src/'manifest.json').read_text('utf-8'))
            for name,expected in manifest['sha256'].items():
                file=confined(src,name)
                if file_digest(file)!=expected:raise ValueError('Evidence integrity check failed')
            if not dst.exists():shutil.copytree(src,dst)
            for name,expected in manifest['sha256'].items():
                if file_digest(confined(dst,name))!=expected:raise ValueError('Copied evidence integrity check failed')
            refs.extend(f'testwins-artifact:{output.name}/{rel}/{name}#sha256:{sha}' for name,sha in manifest['sha256'].items() if name in {'viewport.png','snapshot.json','scan.json'})
        p={'schema':'planfile.ticket-proposal.v1','proposal_id':'testwins:live:'+key,'dedupe_key':'testwins:live:'+project+':'+key,
           'name':'['+f['rule']+'] '+f['title'],
           'description':'Obserwacja GUI bez analizy źródeł aplikacji. Hipotezy poniżej nie są dowodem przyczyny.\n\n'+
                json.dumps({'rule':f['rule'],'selectors':f['selectors'],'matrix':[{'target':r['target'],'state':r['state']} for r in rows],
                    'diagnosis':f.get('diagnosis'),'message':f['message'],'scope':'only explicitly covered states'},ensure_ascii=False,indent=2),
           'priority':f['severity'],'labels':['testwins','live','needs-human','testwins-confirmed' if confirmed else 'testwins-candidate'],
           'files':[],'source':{'tool':'testwins','tool_version':__version__,'finding_id':key,'artifact_digest':artifact_hash},
           'acceptance_criteria':['Potwierdź oczekiwany wygląd/zachowanie przed zmianą kodu.','Sprawdź przynajmniej jedną rozstrzygającą próbę dla hipotezy przyczyny.',
             'Dodaj regresję TestQL lub jawny kontrakt UI.','Uzyskaj dwa porównywalne czyste pomiary w dotkniętych komórkach; pominięte testy nie zamykają zgłoszenia.'],
           'evidence_refs':sorted(set(refs))[:72]}
        validate_producer(p);proposals.append(p)
    atomic_json(output/'proposals.json',proposals)
    return {'proposals':len(proposals),'output':str(output),'published':False,'include_candidates':include_candidates}
