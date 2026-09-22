#!/usr/bin/env python3
"""Build an explicit operator-owned inventory from a file of authorized route paths."""
import argparse
from pathlib import Path
import yaml
p=argparse.ArgumentParser();p.add_argument('--paths',type=Path,required=True);p.add_argument('--base-url',required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();paths=[s.strip() for s in a.paths.read_text().splitlines() if s.strip() and not s.lstrip().startswith('#')]
if not paths or len(paths)>1000 or any(not s.startswith('/') or s.startswith('//') for s in paths):p.error('Provide 1..1000 authorized absolute route paths')
if a.output.exists():p.error('Output already exists')
a.output.write_text(yaml.safe_dump({'schema':'testwins.watch/v1','project':'dev-portal','output':'.testwins/portal',
 'resources':{'max_workers':4,'max_tier':2,'per_origin':1,'max_hot_pages':2},
 'sites':[{'id':'portal','base_url':a.base_url,'pages':list(dict.fromkeys(paths)),'devices':['desktop','tablet','mobile'],'browsers':['chromium'],'interval_s':120}],
 'llm':{'enabled':False}},sort_keys=False))
