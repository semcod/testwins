"""Explicit, private authentication-state input; never use an existing host browser profile."""
from __future__ import annotations
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from .util import origin


def load_state(path: Path, cfg: dict) -> dict:
    if path.is_symlink() or not path.is_file(): raise ValueError('Session must be a regular non-symlink local file')
    if path.stat().st_size>5_000_000: raise ValueError('Session state exceeds 5 MB')
    if os.name=='posix' and path.stat().st_mode & 0o077:
        raise ValueError('Session state is private: set its permissions to 0600')
    data=json.loads(path.read_text('utf-8'))
    if not isinstance(data,dict) or set(data)-{'cookies','origins'}: raise ValueError('Unsupported storage_state document')
    allowed={origin(cfg['base_url']),*(origin(x) for x in cfg['allowed_origins'])}
    hosts={urlsplit(x).hostname for x in allowed}
    if not isinstance(data.get('cookies',[]),list) or not isinstance(data.get('origins',[]),list): raise ValueError('Invalid storage_state lists')
    for item in data.get('origins',[]):
        if not isinstance(item,dict) or origin(item['origin']) not in allowed: raise ValueError('Session contains a non-allowlisted origin')
    for cookie in data.get('cookies',[]):
        if not isinstance(cookie,dict): raise ValueError('Invalid cookie')
        # Exact host only: broad parent-domain cookies must be explicitly authorized as an origin.
        domain=cookie.get('domain','').lstrip('.').lower()
        if domain not in hosts: raise ValueError('Session contains a non-allowlisted cookie domain')
    return data


def state_for(cfg: dict, scene: dict | None = None) -> dict | None:
    name=(scene or {}).get('session',cfg.get('default_session'))
    if name is None:return None
    return load_state(Path(cfg['sessions'][name]['storage_state']),cfg)


def save_private(path: Path, state: dict) -> None:
    """Exclusive creation: no overwriting tokens or following a target symlink."""
    path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as stream:json.dump(state,stream,ensure_ascii=False)


async def capture_session(cfg: dict, path: Path, ready_selector: str, timeout_ms: int = 120000) -> None:
    from playwright.async_api import async_playwright
    from .browser import launch,context_options
    from .runner import guard
    if path.exists() or path.is_symlink(): raise ValueError('Choose a new session file')
    async with async_playwright() as pw:
        async with launch(pw,'chromium',dict(cfg,headless=False)) as (browser,_):
            options=context_options(dict(cfg,default_session=None),cfg['devices'].get('desktop',next(iter(cfg['devices'].values()))),'chromium')
            context=await browser.new_context(**options)
            try:
                await guard(context,cfg)
                page=await context.new_page()
                await page.goto(cfg['base_url'],wait_until='domcontentloaded')
                await page.locator(ready_selector).wait_for(state='visible',timeout=timeout_ms)
                state=await context.storage_state(indexed_db=True)
                save_private(path,state)
            finally:await context.close()
