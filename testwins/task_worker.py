"""Minimal child process boundary. No LLM credentials are needed in an executor."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import json
from .tasks import validate_task, exit_code
from .util import atomic_json, utc_now, digest


def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--request',type=Path,required=True)
    p.add_argument('--project',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(argv);root=a.output.resolve();root.mkdir(parents=True,exist_ok=True)
    try:
        task=validate_task(json.loads(a.request.read_text('utf-8')))
        project=a.project.resolve(strict=True);os.chdir(project)
        Path(os.environ.get('HOME','/tmp')).mkdir(parents=True,exist_ok=True)
        if task['backend']=='testql':
            from .integrations.testql import execute
        elif task['backend']=='terminal':
            from .integrations.terminal import execute
        else:
            from .integrations.desktop import execute
        result={'schema':'testwins.task-result/v1','task_id':task['id'],'project_key':os.environ.get('TW_PROJECT_KEY','unspecified'),'timestamp':utc_now(),**execute(task,project,root)}
    except Exception as exc:
        # Never persist raw command/provider exceptions that could contain credentials.
        result={'schema':'testwins.task-result/v1','status':'incomplete','exception_type':type(exc).__name__,
                'reason':'backend_failed_or_dependency_missing'}
    atomic_json(root/'result.json',result)
    from .task_reporting import write_report
    write_report(root,result)
    return exit_code(result)

if __name__=='__main__':raise SystemExit(main())
