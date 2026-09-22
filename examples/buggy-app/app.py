"""Deliberately defective, dependency-free test application. Synthetic data only."""
import argparse
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
if __name__ == "__main__":
    p=argparse.ArgumentParser();p.add_argument("--port",type=int,default=8080);p.add_argument("--host",default="0.0.0.0");a=p.parse_args()
    server=ThreadingHTTPServer((a.host,a.port),partial(SimpleHTTPRequestHandler,directory=str(Path(__file__).parent)))
    print(f"Fixture listening on {a.host}:{a.port}",flush=True)
    server.serve_forever()
