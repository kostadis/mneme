"""`mneme corpus` — the declared-corpus commands (feature 007, `contracts/cli.md`).

`toc` is the consumer entry point (FR-012): it resolves `corpus.yaml` against the disk on every
call and never reads the snapshot. `current`, `init` and `consumers` register on `app` later.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from hypostasis import config as _hconfig
from mneme.mempalace import authority as _authority
from mneme.mempalace import discover as _discover
from mneme.mempalace import recipe as _recipe
from mneme.mempalace.cli import EXIT_OK, EXIT_RUNTIME, _config_opt, _dir_opt, _load_or_exit
from mneme.mempalace.runner import (
    MempalaceError,
    MempalaceRunner,
    holds_no_palace,
    store_path_problem,
)

from . import api as _api
from . import config as _cconfig
from . import consumers as _consumers
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
    answer = _api.consult(path, _api.campaign_recipe(path))
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
    recipe = _api.campaign_recipe(path)
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


@app.command()
def current(
    campaign: str = typer.Argument(..., help="Campaign name"),
    campaign_dir: str = _dir_opt,
    config: str = _config_opt,
) -> None:
    """List the files the palace holds today, grouped by wing (FR-020). Read-only: it only
    asks `mempalace sources`. Exit non-zero, saying "unknown", if the palace cannot be read."""
    entity = _load_or_exit(config)
    try:
        ref = _discover.resolve(entity, campaign, campaign_dir)
    except _discover.DiscoveryError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(EXIT_RUNTIME) from None
    if not ref.has_authority:
        typer.echo(f"{campaign}: no palace (no .mneme/mempalace.yaml authority)")
        raise typer.Exit(EXIT_OK)
    try:
        cfg = _authority.load(ref.path, mempalace_root=_hconfig.mempalace_root(entity))
    except _authority.AuthorityError as e:
        typer.echo(f"error: unknown: authority does not load: {'; '.join(e.problems)}", err=True)
        raise typer.Exit(EXIT_RUNTIME) from None
    if cfg.store is not None and (problem := store_path_problem(Path(cfg.store.path))):
        typer.echo(f"error: unknown: {problem}", err=True)
        raise typer.Exit(EXIT_RUNTIME)
    if cfg.store is None or holds_no_palace(Path(cfg.store.path)):
        typer.echo(f"{campaign}: no palace (the store is not provisioned)")
        raise typer.Exit(EXIT_OK)
    runner = MempalaceRunner.for_entity(entity)
    try:
        rows = runner.sources(cfg.store.path) if runner.supports_corpus_read() else None
    except MempalaceError as e:  # the capability probe could not run: unknown, not too old
        typer.echo(f"error: unknown: {e}", err=True)
        raise typer.Exit(EXIT_RUNTIME) from None
    if rows is None:
        why = runner.last_error or "`mempalace sources` failed, or this mempalace lacks it"
        typer.echo(f"error: unknown: the palace for {campaign} could not be read ({why})",
                   err=True)
        raise typer.Exit(EXIT_RUNTIME)
    root = ref.path.resolve()
    by_wing: dict[str, list[str]] = {}
    for r in rows:
        p = Path(r.source_file)
        try:
            shown = p.resolve().relative_to(root).as_posix()
        except (ValueError, OSError):
            shown = r.source_file
        by_wing.setdefault(r.wing, []).append(shown)
    if not by_wing:
        typer.echo(f"{campaign}: the palace holds no files")
    for wing in sorted(by_wing):
        files = sorted(by_wing[wing])
        typer.echo(f"{wing}: {len(files)} file(s)")
        for f in files:
            typer.echo(f"  {f}")
    raise typer.Exit(EXIT_OK)


def _skeleton(campaign: str) -> str:
    lines = [
        f"# Declared corpus for {campaign} (feature 007). Nothing is mined from a path until you",
        "# declare it. Uncomment a kind and list its dirs/files (campaign-relative, POSIX).",
        "# Check with `mneme corpus check`; see what the palace holds with `mneme corpus current`.",
        f"campaign: {campaign}",
        "",
        "# kinds:",
    ]
    for k in _recipe.current().kinds:
        lines += [f"#   {k.name}:", "#     dirs: []", "#     files: []"]
    lines += ["", "# Kinds specific to this campaign (not a standard kind name):",
              "# campaign_kinds:", ""]
    return "\n".join(lines)


@app.command()
def init(
    campaign: str = typer.Argument(..., help="Campaign name"),
    campaign_dir: str = _dir_opt,
    config: str = _config_opt,
) -> None:
    """Write a skeleton .mneme/corpus.yaml: every standard kind as a comment, no paths.
    Refuses if one already exists."""
    path = _campaign_dir(config, campaign, campaign_dir)
    target = _cconfig.corpus_path(path)
    if target.exists():
        typer.echo(f"error: {target} already exists; `corpus init` never overwrites", err=True)
        raise typer.Exit(EXIT_RUNTIME)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_skeleton(campaign))
    typer.echo(f"wrote {target} (edit it, then `mneme corpus check {campaign}`)")
    raise typer.Exit(EXIT_OK)


EXIT_INVALID = 2


@app.command()
def consumers(
    noncompliant: bool = typer.Option(False, "--noncompliant",
                                      help="Only partial and non-compliant consumers"),
    as_json: bool = typer.Option(False, "--json", help="Print JSON"),
) -> None:
    """List the known consumers of campaign files and how compliant each is (FR-023).
    Exit 0, or 2 when consumers.yaml is invalid."""
    try:
        rows = _consumers.load(_consumers.DEFAULT)
    except _consumers.ConsumersError as e:
        typer.echo("error: consumers.yaml is invalid", err=True)
        for p in e.problems:
            typer.echo(f"  - {p}", err=True)
        raise typer.Exit(EXIT_INVALID) from None
    if noncompliant:
        rows = _consumers.noncompliant(rows)
    if as_json:
        typer.echo(json.dumps([
            {"name": c.name, "repo": c.repo, "entry": c.entry, "kinds": list(c.kinds),
             "mode": c.mode, "compliance": _consumers.compliance(c)} for c in rows], indent=2))
    else:
        for c in rows:
            typer.echo(f"{c.name} [{c.repo}] {c.entry} kinds={','.join(c.kinds)} "
                       f"mode={c.mode} {_consumers.compliance(c)}")
    raise typer.Exit(EXIT_OK)
