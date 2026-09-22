#!/usr/bin/env python3
"""Explicit offline renderer fixture; does not disable browser HTTP policies."""
from __future__ import annotations
import asyncio,json,os,re,sys
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from playwright.async_api import Page
from testwins.config import load
from testwins.runner import run
from testwins.verification import verify_run
ROOT=Path(__file__).resolve().parents[1]

async def offline(page,url,**kwargs):
    parsed=urlsplit(url)
    if parsed.netloc!='sut:8080' or parsed.path not in ('/','/docs/','/privacy/'):
        raise ValueError('Only explicitly bundled landing fixtures are allowed')
    text=(ROOT/'landing/static'/(parsed.path.lstrip('/')+'index.html')).read_text('utf-8')
    text=re.sub(r'<link\b[^>]*>','',text,flags=re.I)
    text=re.sub(r'<script\b[^>]*src=[^>]*>\s*</script>','',text,flags=re.I)
    await page.set_content(text,wait_until='domcontentloaded')
    await page.add_style_tag(content=(ROOT/'landing/static/style.css').read_text())
    await page.add_script_tag(content=(ROOT/'landing/static/app.js').read_text())
    return None

def main():
    output=ROOT/'verification/landing-runs'
    cfg=load(ROOT/'landing/tests/audit.yaml',matrix='chromium',headless=True)
    cfg['executables']['chromium']=os.environ.get('CHROMIUM_EXECUTABLE','/usr/bin/chromium');cfg['axe']['enabled']=False
    cfg['capture']['timeout_ms']=3500;cfg['capture']['max_cell_seconds']=240
    os.environ['TW_VERIFICATION_FIXTURE']='offline-rendered-landing-no-http-navigation'
    try:
        with patch.object(Page,'goto',offline):root=asyncio.run(run(cfg,output))
    finally:os.environ.pop('TW_VERIFICATION_FIXTURE',None)
    report=json.loads((root/'report.json').read_text());checks=report['checks']
    summary={'schema':'testwins.local-verification/v1','directory':str(root.relative_to(ROOT)),
       'fixture_mode':report['environment']['fixture_mode'],'coverage':report['coverage'],
       'summary':report['summary'],'checks':len(checks),'checks_passed':sum(c['status']=='passed' for c in checks),
       'snapshots':len(report['snapshots']),'environment':report['environment'],'integrity':verify_run(root),
       'browser_versions':sorted({c.get('version','') for c in report['cells']}),
       'not_verified':['HTTP navigation','Docker/noVNC','full nine-cell matrices','TestQL SDK','axe-core','remote vision models','actual YOLO weights']}
    (ROOT/'verification/landing-result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
    assert summary['coverage']['incomplete_cells']==0,report['cells']
    assert report['gate']['exit_code']==0,report['gate']
    assert len(checks)==24,checks
    assert all(c['status']=='passed' for c in checks),checks
    return 0
if __name__=='__main__':raise SystemExit(main())
