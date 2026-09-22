#!/usr/bin/env python3
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from testwins.llm import validate_response, review, env_file
from testwins.util import utc_now

def main():
    values=env_file()
    source=values.get('RUN')
    if not source:raise ValueError('Set RUN to an audit directory or image')
    out=review(Path(source),Path('analysis')/utc_now().replace(':','').replace('.','-'),values)
    print(out)
    import json
    return 2 if json.loads((out/'vision.json').read_text())['errors'] else 0
if __name__=='__main__':raise SystemExit(main())
