"""Static reports only; never execute evidence HTML as an application.
Bind it to loopback on the host through Compose. No write API, uploads or symlink escape.
"""
from __future__ import annotations
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

class Reports(SimpleHTTPRequestHandler):
    def translate_path(self,path):
        candidate=Path(super().translate_path(path)).resolve()
        root=Path(self.directory).resolve()
        return str(candidate if candidate.is_relative_to(root) else root/'.denied')
    def end_headers(self):
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        if self.path.split('?',1)[0].endswith('rendered.html'):
            self.send_header('Content-Disposition','attachment; filename="rendered.html"')
            self.send_header('Content-Security-Policy',"sandbox; default-src 'none'")
        super().end_headers()
    def log_message(self,*args):pass

def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=8088)
    a=p.parse_args();a.directory.mkdir(parents=True,exist_ok=True)
    ThreadingHTTPServer((a.host,a.port),partial(Reports,directory=str(a.directory))).serve_forever()
if __name__=='__main__':main()
