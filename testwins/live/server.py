from __future__ import annotations
import json
import threading
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit,parse_qs


class Server:
    def __init__(self,store,host='127.0.0.1',port=9067,*,allow_expose=False):
        if host not in {'127.0.0.1','localhost'} and not allow_expose:raise ValueError('Non-loopback binding requires explicit --allow-expose; use loopback port publishing in Docker')
        self.stop=threading.Event();self.store=store;self.thread=None;self.streams=threading.BoundedSemaphore(16)
        owner=self
        class Handler(BaseHTTPRequestHandler):
            protocol_version='HTTP/1.1'
            def setup(self):
                super().setup();self.connection.settimeout(3)
            def log_message(self,*args):pass
            def reply(self,code,data,kind):
                self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)))
                self.send_header('Connection','close');self.close_connection=True
                self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'")
                self.end_headers();self.wfile.write(data)
            def do_GET(self):
                # Basic DNS-rebinding guard. No cookies, tokens in query strings, write API or credentialed CORS.
                hostname=self.headers.get('Host','').split(':')[0].lower()
                if hostname not in {'127.0.0.1','localhost',host}:
                    self.reply(403,b'Invalid host','text/plain');return
                p=urlsplit(self.path)
                if p.path=='/':self.reply(200,Path(__file__).with_name('dashboard.html').read_bytes(),'text/html; charset=utf-8')
                elif p.path=='/api/status':self.reply(200,json.dumps(owner.store.status(compact=True,display_limit=500),ensure_ascii=False).encode(),'application/json; charset=utf-8')
                elif p.path=='/events':
                    if not owner.streams.acquire(blocking=False):self.reply(503,b'Stream limit','text/plain');return
                    try:
                        try:cursor=max(0,int(self.headers.get('Last-Event-ID') or parse_qs(p.query).get('after',['0'])[0]))
                        except ValueError:self.reply(400,b'Invalid cursor','text/plain');return
                        self.send_response(200);self.send_header('Content-Type','text/event-stream; charset=utf-8')
                        self.send_header('Cache-Control','no-cache');self.send_header('Connection','close');self.send_header('X-Accel-Buffering','no');self.end_headers()
                        self.connection.settimeout(3)
                        earliest,latest=owner.store.event_bounds()
                        if cursor and earliest>cursor+1:
                            self.wfile.write(('data: '+json.dumps({'kind':'stream_gap','payload':{'after':cursor,'oldest':earliest,'action':'reload /api/status'}})+'\n\n').encode());cursor=earliest-1
                        if cursor>latest:cursor=0
                        if not cursor:cursor=max(0,latest-50)
                        ping=0
                        while not owner.stop.is_set():
                            earliest,_=owner.store.event_bounds()
                            if earliest>cursor+1:
                                self.wfile.write(('data: '+json.dumps({'kind':'stream_gap','payload':{'after':cursor,'oldest':earliest,'action':'reload /api/status'}})+'\n\n').encode());cursor=earliest-1
                            rows=owner.store.events(cursor)
                            for e in rows:
                                self.wfile.write(('id: '+str(e['id'])+'\ndata: '+json.dumps(e,ensure_ascii=False)+'\n\n').encode());cursor=e['id']
                            if rows or time.monotonic()-ping>10:
                                self.wfile.write(b': heartbeat\n\n');self.wfile.flush();ping=time.monotonic()
                            owner.stop.wait(.25)
                    except (OSError,TimeoutError):pass
                    finally:owner.streams.release();self.close_connection=True
                else:self.reply(404,b'Not found','text/plain')
            def do_POST(self):self.reply(405,b'Read-only API','text/plain')
        self.http=ThreadingHTTPServer((host,port),Handler);self.http.daemon_threads=False
    @property
    def port(self):return self.http.server_port
    def start(self):self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
    def close(self):
        self.stop.set();self.http.shutdown();self.http.server_close()
        if self.thread:self.thread.join(3)
