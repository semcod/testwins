"""Optional Testwins GUI monitoring commands. No import-time scanning or model calls.

This is an additive WUP integration: ``wup gui watch``, not a monkey patch of
WUP's HTTP watcher or TestQL execution semantics.
"""
from pathlib import Path
from typing import Optional
import json
import typer

app=typer.Typer(help='Continuous rendered-GUI diagnostics powered by Testwins',no_args_is_help=True)


def _config(project:Path,config:Optional[Path]):
    project=project.resolve()
    return project, (config if config and config.is_absolute() else project/(config or Path('testwins.watch.yaml'))).resolve()


@app.command()
def watch(project:Path=typer.Argument(Path('.')),config:Optional[Path]=typer.Option(None),
          output:Optional[Path]=typer.Option(None),once:bool=typer.Option(False),
          serve:bool=typer.Option(True,'--serve/--no-serve'),port:int=typer.Option(9067),quiet:bool=typer.Option(False)):
    """Watch project changes and rendered GUI. Opt-in; never starts paid LLM by default."""
    try:
        from testwins.live.cli import run_watch
    except ImportError:
        typer.echo('Install the supplied Testwins 0.3 distribution with the [live] extra in the WUP environment.',err=True)
        raise typer.Exit(2)
    root,path=_config(project,config)
    try:code=run_watch(path,root=root,output=output,once=once,serve=serve,port=port,quiet=quiet)
    except (ValueError,OSError,RuntimeError) as exc:
        typer.echo(f'GUI monitor: {type(exc).__name__}: {exc}',err=True);raise typer.Exit(2)
    raise typer.Exit(code)


@app.command()
def status(project:Path=typer.Argument(Path('.')),config:Optional[Path]=typer.Option(None)):
    """Print persistent GUI incidents, confidence, coverage and probable causes."""
    try:
        from testwins.live.config import load
        from testwins.live.cli import dispatch
        from argparse import Namespace
        root,path=_config(project,config);cfg=load(path,project_root=root)
        raise typer.Exit(dispatch(Namespace(command='live-status',directory=cfg.output)))
    except (ValueError,OSError,ImportError) as exc:
        typer.echo(f'GUI status: {exc}',err=True);raise typer.Exit(2)


@app.command()
def capacity(project:Path=typer.Argument(Path('.')),config:Optional[Path]=typer.Option(None),
             seconds_per_cell:float=typer.Option(2),interval:float=typer.Option(60)):
    """Estimate inventory capacity. This is an analytical model, not a benchmark."""
    from testwins.live.config import load,number
    from testwins.live.policy import capacity as estimate
    root,path=_config(project,config);cfg=load(path,project_root=root)
    number(seconds_per_cell,.001,3600,'seconds_per_cell');number(interval,1,86400,'interval')
    typer.echo(json.dumps(estimate(len(cfg.targets),seconds_per_cell,cfg.max_workers,interval),indent=2))


@app.command('export')
def export_command(project:Path=typer.Argument(Path('.')),output:Path=typer.Option(...),config:Optional[Path]=typer.Option(None)):
    """Export confirmed GUI tickets and immutable evidence, without writing Planfile."""
    from testwins.live.config import load
    from testwins.live.cli import dispatch
    from argparse import Namespace
    root,path=_config(project,config);cfg=load(path,project_root=root)
    raise typer.Exit(dispatch(Namespace(command='live-export',directory=cfg.output,output=output,project=cfg.project,include_candidates=False)))
