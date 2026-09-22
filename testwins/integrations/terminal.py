"""Bounded POSIX terminal tests, using Pexpect rather than a home-grown PTY driver."""
from __future__ import annotations
import re
from pathlib import Path
from ..util import atomic_json, confined


class OutputBudget:
    """Pexpect read sink counts even unmatched output; raw terminal data is never retained."""
    def __init__(self, limit: int): self.limit=limit;self.used=0
    def write(self, data):
        self.used+=len(data.encode('utf-8')) if isinstance(data,str) else len(data)
        if self.used>self.limit: raise ValueError('Terminal output budget exceeded')
    def flush(self): pass


def execute(task: dict, project: Path, output: Path) -> dict:
    import pexpect
    command=task.get('command');args=task.get('args',[])
    if not isinstance(command,str) or not command or not isinstance(args,list) or not all(isinstance(x,str) for x in args):
        raise ValueError('Terminal task needs command and string args (no implicit shell)')
    limit=task.get('max_output_bytes',262144)
    if type(limit) is not int or not 1024<=limit<=2_000_000:raise ValueError('Invalid terminal output limit')
    steps=task['steps']
    for s in steps:
        if not isinstance(s,dict) or set(s)-{'action','value','timeout_seconds'} or s.get('action') not in {'send','expect','eof'}:
            raise ValueError('Invalid terminal step')
        if s['action']!='eof' and (not isinstance(s.get('value'),str) or len(s['value'])>4000):raise ValueError('Invalid terminal text')
        if type(s.get('timeout_seconds',10)) not in (int,float) or not 0<s.get('timeout_seconds',10)<=60:raise ValueError('Invalid terminal timeout')
        if s['action']=='expect':re.compile(s['value'])
    cwd=confined(project,task.get('cwd','.'))
    child=pexpect.spawn(command,args,cwd=str(cwd),encoding='utf-8',codec_errors='replace',
                        timeout=task.get('step_timeout_ms',10000)/1000,maxread=4096,searchwindowsize=65536)
    records=[];budget=OutputBudget(limit);child.logfile_read=budget;observed_eof=False
    try:
        for i,s in enumerate(steps):
            action=s['action'];status='passed'
            try:
                if action=='send':child.sendline(s['value'])
                elif action=='expect':child.expect(s['value'],timeout=s.get('timeout_seconds',10))
                else:child.expect(pexpect.EOF,timeout=s.get('timeout_seconds',10));observed_eof=True
            except (pexpect.TIMEOUT,pexpect.EOF):status='failed'
            records.append({'step':i+1,'action':action,'status':status})
            if status=='failed':break
    finally:child.close(force=True)
    failed=any(s['status']=='failed' for s in records)
    exit_ok=(child.exitstatus==task.get('expected_exit_code',0)) if observed_eof else None
    if exit_ok is False:failed=True
    atomic_json(output/'terminal-steps.json',records)
    return {'backend':'terminal','status':'failed' if failed else 'passed',
            'steps':len(steps),'executed':len(records),'observed_bytes':budget.used,'exit_status':child.exitstatus,
            'exit_code_asserted':observed_eof,'exit_code_matched':exit_ok}
