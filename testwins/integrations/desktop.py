"""Explicit screenshot-only desktop actions in an isolated X11 display (or opted-in local desktop)."""
from __future__ import annotations
import subprocess
import time
from pathlib import Path
from ..cv import match_template
from ..util import atomic_json, confined, file_digest


def screenshot(path: Path) -> None:
    import mss
    import mss.tools
    with mss.mss() as screen:
        shot=screen.grab(screen.monitors[0]);mss.tools.to_png(shot.rgb,shot.size,output=str(path))


def execute(task: dict, project: Path, output: Path) -> dict:
    import pyautogui as gui
    gui.FAILSAFE=True;gui.PAUSE=.1
    actions={'capture','click','click_template','assert_template','press','write','wait'}
    for s in task['steps']:
        if not isinstance(s,dict) or set(s)-{'action','x','y','template','threshold','key','text','seconds'} or s.get('action') not in actions:
            raise ValueError('Invalid closed desktop step')
        if s['action'] in ('click_template','assert_template'):
            confined(project,s['template']).resolve(strict=True)
        if s['action']=='press' and s.get('key') not in gui.KEYBOARD_KEYS:raise ValueError('Invalid desktop key')
        if s['action']=='write' and (not isinstance(s.get('text'),str) or len(s['text'])>2000):raise ValueError('Invalid desktop input')
        if s['action']=='wait' and not 0<=float(s.get('seconds',.1))<=10:raise ValueError('Invalid desktop delay')
    app=None;records=[]
    try:
        if task.get('command'):
            args=task.get('args',[])
            if not isinstance(args,list) or not all(isinstance(x,str) for x in args):raise ValueError('Invalid desktop argv')
            app=subprocess.Popen([task['command'],*args],cwd=project,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            time.sleep(.5)
        for i,s in enumerate(task['steps']):
            before=output/f'desktop-{i+1:03d}-before.png';screenshot(before)
            action=s['action'];record={'step':i+1,'action':action,'before':before.name,'before_sha256':file_digest(before),'status':'passed'}
            if action in ('click_template','assert_template'):
                match=match_template(before,confined(project,s['template']),threshold=s.get('threshold',.9));record['match']=match
                if not match['found']:record['status']='failed'
                elif action=='click_template':
                    b=match['box'];gui.click(b['x']+b['width']/2,b['y']+b['height']/2)
            elif action=='click':
                w,h=gui.size();x,y=s['x'],s['y']
                if type(x) is not int or type(y) is not int or not 0<=x<w or not 0<=y<h:raise ValueError('Click outside display')
                gui.click(x,y)
            elif action=='press':gui.press(s['key'])
            elif action=='write':gui.write(s['text'],interval=.02)
            elif action=='wait':time.sleep(float(s.get('seconds',.1)))
            after=output/f'desktop-{i+1:03d}-after.png';screenshot(after)
            record.update(after=after.name,after_sha256=file_digest(after));records.append(record)
            if record['status']=='failed':break
    finally:
        if app:
            app.terminate()
            try:app.wait(3)
            except subprocess.TimeoutExpired:app.kill();app.wait()
    atomic_json(output/'desktop-steps.json',records)
    return {'backend':'desktop','status':'failed' if any(r['status']=='failed' for r in records) else 'passed',
            'steps':len(task['steps']),'executed':len(records),'display_backend':'pyautogui+mss',
            'privacy':'Desktop images are NOT DOM-masked. Use only a disposable desktop and synthetic data.'}
