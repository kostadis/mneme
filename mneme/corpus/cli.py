"""`mneme corpus` — the declared-corpus commands (feature 007, `contracts/cli.md`).

`toc` is the consumer entry point (FR-012): it resolves `corpus.yaml` against the disk on every
call and never reads the snapshot. `current`, `init` and `consumers` register on `app` later.
"""

from __future__ import annotations

import json

import typer

from mneme.mempalace import discover as _discover
from mneme.mempalace import recipe as _recipe
from mneme.mempalace.cli import EXIT_OK, EXIT_RUNTIME, _config_opt, _dir_opt, _load_or_exit

from . import api as _api
from . import toc as _toc

app = typer.Typer(no_args_is_help=True, help="Declared campaign corpus: check, resolve, inspect.")


def _campaign_dir(config: str, campaign: str, campaign_dir: str | None):
    entity = _load_or_exit(config)
    try:
        return _discover.resolve(entity, campaign, campaign_dir).path
    except _discover.DiscoveryError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(EXIT_RUNTIME) from None


def _refuse(answer: dict) -> typer.Exit:
    typer.echo(f"error: {answer['detail']}", err=True)
    for f in answer.get("findings", []):
        typer.echo(f"  - {f['code']}: {f['detail']}" + (f" [{f['path']}]" if f.get("path") else ""),
                   err=True)
    return typer.Exit(EXIT_RUNTIME)


@app.command()
def check(
    campaign: str = typer.Argument(..., help="Campaign name"),
    campaign_dir: str = _dir_opt,
    config: str = _config_opt,
) -> None:
    """Validate the configuration and print the resolution per kind. Exit 0 iff valid."""
    path = _campaign_dir(config, campaign, campaign_dir)
    answer = _api.consult(path, _recipe.current())
    if "error" in answer:
        raise _refuse(answer)
    for name, k in answer["toc"]["kinds"].items():
        typer.echo(f"{name} ({k['trust']}): {len(k['files'])} file(s)")
        for label, items in (("not materialized", k["not_materialized"]),
                             ("missing", k["missing"])):
            for item in items:
                typer.echo(f"  {label}: {item}")
    typer.echo("corpus is valid")
    raise typer.Exit(EXIT_OK)


@app.command()
def toc(
    campaign: str = typer.Argument(..., help="Campaign name"),
    kind: str = typer.Option(None, "--kind", "-k", help="Restrict to one kind"),
    as_json: bool = typer.Option(False, "--json", help="Print the TOC JSON (toc-json contract)"),
    write: bool = typer.Option(False, "--write", help="Also refresh .mneme/corpus.toc.json"),
    campaign_dir: str = _dir_opt,
    config: str = _config_opt,
) -> None:
    """Resolve the corpus NOW (never from the snapshot) and print it. Non-zero if the
    configuration is invalid or the kind is not declared."""
    path = _campaign_dir(config, campaign, campaign_dir)
    recipe = _recipe.current()
    answer = _api.consult(path, recipe, kind)
    if "error" in answer:
        raise _refuse(answer)
    doc = answer["toc"]
    if write:
        full = doc if kind is None else _api.fresh(path, recipe)
        _toc.write(path, full)
    if as_json:
        typer.echo(json.dumps(doc, indent=2))
    else:
        for name, k in doc["kinds"].items():
            typer.echo(f"{name} ({k['trust']}): {len(k['files'])} file(s)")
            for f in k["files"]:
                typer.echo(f"  {f['path']}")
    raise typer.Exit(EXIT_OK)
