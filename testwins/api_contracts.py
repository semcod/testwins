"""Opt-in HTTP contracts, separate from the rendered-only GUI diagnosis and device matrix."""
from __future__ import annotations
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from urllib.parse import urljoin
from xml.etree import ElementTree as ET
import yaml
from .util import atomic_json, origin, file_digest, utc_now


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):return None


def pointer(data, path: str):
    if path=='':return data
    if not path.startswith('/'):raise ValueError('JSON pointer must start with /')
    for token in path[1:].split('/'):
        token=token.replace('~1','/').replace('~0','~')
        if isinstance(data,list):
            if not re.fullmatch(r'0|[1-9][0-9]*',token):raise KeyError(token)
            data=data[int(token)]
        else:data=data[token]
    return data


def load(path: Path) -> dict:
    if path.stat().st_size>2_000_000:raise ValueError('API config too large')
    cfg=yaml.safe_load(path.read_text('utf-8'))
    allowed={'schema','id','base_url','timeout_seconds','max_body_bytes','headers','header_env','requests'}
    if not isinstance(cfg,dict) or set(cfg)-allowed or cfg.get('schema')!='testwins.api/v1':raise ValueError('Invalid API contract')
    if not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}',cfg.get('id','')):raise ValueError('Invalid API id')
    base=origin(cfg['base_url'])
    cfg.setdefault('timeout_seconds',10);cfg.setdefault('max_body_bytes',1_000_000)
    for key,low,high in [('timeout_seconds',1,60),('max_body_bytes',1,10_000_000)]:
        if type(cfg[key]) is not int or not low<=cfg[key]<=high:raise ValueError('Invalid '+key)
    for key in ('headers','header_env'):
        cfg.setdefault(key,{})
        if not isinstance(cfg[key],dict):raise ValueError('Invalid '+key)
        for name,value in cfg[key].items():
            if not re.fullmatch(r'[A-Za-z0-9-]+',name) or not isinstance(value,str) or '\n' in value or '\r' in value:
                raise ValueError('Invalid header')
            if name.lower() in ('host','content-length','transfer-encoding','connection'):raise ValueError('Transport headers are managed by the client')
            if key=='header_env' and not re.fullmatch('[A-Z_][A-Z0-9_]*',value):raise ValueError('Invalid environment variable')
    requests=cfg.get('requests')
    if not isinstance(requests,list) or not 1<=len(requests)<=50:raise ValueError('API suite requires 1..50 requests')
    names=set()
    for req in requests:
        if not isinstance(req,dict) or set(req)-{'id','path','method','body','allow_mutation','expect'}:raise ValueError('Invalid request')
        name=req.get('id','')
        if not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}',name) or name in names:raise ValueError('Invalid/duplicate request id')
        names.add(name)
        if not isinstance(req.get('path'),str) or origin(urljoin(cfg['base_url'],req['path']))!=base:raise ValueError('API request leaves the configured origin')
        req.setdefault('method','GET')
        if req['method'] not in {'GET','HEAD','POST','PUT','PATCH','DELETE'}:raise ValueError('Unsupported HTTP method')
        if req['method'] not in ('GET','HEAD') and req.get('allow_mutation') is not True:raise ValueError('Mutation requires explicit allow_mutation')
        if req['method'] in ('GET','HEAD') and 'body' in req:raise ValueError('GET/HEAD body forbidden')
        if len(json.dumps(req.get('body'),allow_nan=False))>1_000_000:raise ValueError('Request body too large')
        exp=req.get('expect',{})
        if not isinstance(exp,dict) or set(exp)-{'status','json_equals','headers','json_min_length','json_any'}:raise ValueError('Invalid API expectation')
        if type(exp.get('status')) is not int or not 100<=exp['status']<=599:raise ValueError('Explicit expected status required')
        if not isinstance(exp.get('json_equals',{}),dict):raise ValueError('json_equals must be a map of JSON pointers')
        for key in exp.get('json_equals',{}):
            if not isinstance(key,str) or key and not key.startswith('/'):raise ValueError('Invalid JSON pointer')
        if not isinstance(exp.get('headers',{}),dict) or not all(isinstance(k,str) and isinstance(v,str) for k,v in exp.get('headers',{}).items()):raise ValueError('Invalid expected headers')
        if not isinstance(exp.get('json_min_length',{}),dict):raise ValueError('json_min_length must be a map')
        for key,value in exp.get('json_min_length',{}).items():
            if not isinstance(key,str) or not key.startswith('/') or type(value) is not int or not 0<=value<=100000:raise ValueError('Invalid minimum JSON length')
        if not isinstance(exp.get('json_any',[]),list):raise ValueError('json_any must be a list')
        for rule in exp.get('json_any',[]):
            if not isinstance(rule,dict) or set(rule)!={'path','field','contains'} or not all(isinstance(v,str) for v in rule.values()) or not rule['path'].startswith('/'):
                raise ValueError('Invalid JSON array predicate')
    return cfg


def run(path: Path, output: Path, *, approve_mutations: bool=False) -> Path:
    cfg=load(path)
    if any(r['method'] not in ('GET','HEAD') for r in cfg['requests']) and not approve_mutations:
        raise ValueError('This API suite can mutate state. Review it and explicitly use --approve-mutations against disposable data.')
    headers=dict(cfg['headers'])
    for key,env in cfg['header_env'].items():
        value=os.environ.get(env)
        if not value or '\r' in value or '\n' in value:raise ValueError('Missing or invalid API header environment variable: '+env)
        headers[key]=value
    root=output/('api-'+utc_now().replace(':','').replace('.','-')+'-'+uuid.uuid4().hex[:8])
    root.mkdir(parents=True,exist_ok=False)
    report={'schema':'testwins.api-report/v1','id':cfg['id'],'scope':'explicit API contracts, once per request; not GUI or device testing',
            'created':utc_now(),'config_sha256':file_digest(path),'status':'incomplete',
            'plan':[r['id'] for r in cfg['requests']],'checks':[{'id':r['id'],'status':'not_run'} for r in cfg['requests']],
            'privacy':'No request headers, bodies, response bodies or raw exceptions retained'}
    atomic_json(root/'report.json',report)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    for req,check in zip(cfg['requests'],report['checks']):
        started=time.monotonic()
        response=None
        try:
            body=None if 'body' not in req else json.dumps(req['body'],allow_nan=False).encode()
            req_headers=dict(headers)
            if body is not None:req_headers.setdefault('Content-Type','application/json')
            request=urllib.request.Request(urljoin(cfg['base_url'],req['path']),data=body,headers=req_headers,method=req['method'])
            try:response=opener.open(request,timeout=cfg['timeout_seconds'])
            except urllib.error.HTTPError as exc:response=exc
            raw=response.read(cfg['max_body_bytes']+1)
            if len(raw)>cfg['max_body_bytes']:raise ValueError('Response capture limit exceeded')
            check.update(response_status=response.code,response_bytes=len(raw),response_sha256=hashlib.sha256(raw).hexdigest())
            reasons=[];exp=req['expect']
            if response.code!=exp['status']:reasons.append('status_mismatch')
            if any(response.headers.get(k)!=v for k,v in exp.get('headers',{}).items()):reasons.append('header_mismatch')
            if any(exp.get(k) for k in ('json_equals','json_min_length','json_any')):
                try:
                    payload=json.loads(raw)
                    for key,value in exp.get('json_equals',{}).items():
                        actual=pointer(payload,key)
                        if json.dumps(actual,sort_keys=True)!=json.dumps(value,sort_keys=True):reasons.append('json_mismatch')
                    for key,value in exp.get('json_min_length',{}).items():
                        actual=pointer(payload,key)
                        if not isinstance(actual,(list,dict,str)) or len(actual)<value:reasons.append('json_length')
                    for rule in exp.get('json_any',[]):
                        actual=pointer(payload,rule['path'])
                        if not isinstance(actual,list) or not any(isinstance(x,dict) and isinstance(x.get(rule['field']),str) and rule['contains'] in x[rule['field']] for x in actual):reasons.append('json_array_predicate')
                except (ValueError,KeyError,IndexError,TypeError):reasons.append('json_missing_or_invalid')
            check.update(status='failed' if reasons else 'passed',reasons=sorted(set(reasons)))
        except Exception as exc:
            check.update(status='incomplete',exception_type=type(exc).__name__)
        finally:
            if response is not None:response.close()
            check['duration_ms']=round((time.monotonic()-started)*1000,2)
            atomic_json(root/'report.json',report)
    statuses={c['status'] for c in report['checks']}
    report['status']='incomplete' if statuses-{'passed','failed'} else 'failed' if 'failed' in statuses else 'passed'
    report['exit_code']={'passed':0,'failed':1,'incomplete':2}[report['status']]
    atomic_json(root/'report.json',report)
    suite=ET.Element('testsuite',name='testwins.api',tests=str(len(report['checks'])),failures=str(sum(c['status']=='failed' for c in report['checks'])),errors=str(sum(c['status']=='incomplete' for c in report['checks'])))
    for c in report['checks']:
        test=ET.SubElement(suite,'testcase',name=c['id'],classname='api.contract')
        if c['status']!='passed':ET.SubElement(test,'failure' if c['status']=='failed' else 'error',message=c['status'])
    ET.ElementTree(suite).write(root/'junit.xml',encoding='utf-8',xml_declaration=True)
    return root
