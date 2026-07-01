"""The `mneme mp` command group — manage per-campaign mempalaces.

Reads observe the active checkout; writes go through the private working copy
(never the active checkout — FR-018). Commands are added per user story below.
"""

from __future__ import annotations

import typer

from hypostasis import config as cfg
from hypostasis.models import ConfigEntity

EXIT_OK = 0
EXIT_RUNTIME = 1
EXIT_INVALID_CONFIG = 2

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Manage per-campaign mempalaces (status/refresh/publish/adopt/migrate/bootstrap).",
)

_config_opt = typer.Option(
    str(cfg.default_config_path()), "--config", "-c", help="Path to hypostasis.yaml"
)

# GH #27 — resolve an ambiguous campaign name (present in >1 declared tree) to an explicit
# workspace path. Mirrors `mneme up`/`mneme integrate`.
_dir_opt = typer.Option(
    None, "--dir", "-d", help="Explicit campaign workspace path (overrides the name lookup)"
)


def _load_or_exit(config_path: str) -> ConfigEntity:
    try:
        return cfg.load(config_path)
    except FileNotFoundError:
        typer.echo(f"error: env config not found: {config_path}", err=True)
        raise typer.Exit(EXIT_INVALID_CONFIG) from None
    except cfg.ConfigError as e:
        typer.echo("error: invalid hypostasis.yaml:", err=True)
        for problem in e.problems:
            typer.echo(f"  - {problem}", err=True)
        raise typer.Exit(EXIT_INVALID_CONFIG) from None


# ── refresh (US1) ───────────────────────────────────────────────────────────


@app.command()
def refresh(
    campaign: str = typer.Argument(None, help="Campaign name (omit with --all)"),
    campaign_dir: str = _dir_opt,
    all_: bool = typer.Option(False, "--all", help="Refresh every discovered campaign"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the per-wing mine plan"),
    config: str = _config_opt,
) -> None:
    """(Re)build campaign indexes from each campaign's own wing configuration."""
    from . import discover as _discover
    from . import refresh as _refresh

    entity = _load_or_exit(config)
    if not campaign and not campaign_dir and not all_:
        typer.echo("error: give a CAMPAIGN, --dir, or --all", err=True)
        raise typer.Exit(EXIT_RUNTIME)
    try:
        results = _refresh.refresh(
            entity,
            campaign=None if all_ else campaign,
            campaign_dir=None if all_ else campaign_dir,
            dry_run=dry_run,
        )
    except _discover.DiscoveryError as e:
        typer.echo(f"FAIL refresh: {e}", err=True)
        raise typer.Exit(EXIT_RUNTIME) from None
    rc = EXIT_OK
    for r in results:
        typer.echo(r.line())
        if r.failed:
            rc = EXIT_RUNTIME
    raise typer.Exit(rc)


# ── status (US2) ──────────────────────────────────────────────────────────────


@app.command()
def status(
    campaign: str = typer.Argument(None, help="Campaign name (omit for all)"),
    campaign_dir: str = _dir_opt,
    strict: bool = typer.Option(False, "--strict", help="Treat a stale index as a failure"),
    no_proposals: bool = typer.Option(False, "--no-proposals", help="Skip the proposal to-do list"),
    no_fetch: bool = typer.Option(False, "--no-fetch", help="Don't fetch when listing proposals"),
    config: str = _config_opt,
) -> None:
    """Report observed per-campaign conformance (built / stale / divergent + why) and the
    git-level to-do list of mneme proposal branches awaiting integration (GH #14)."""
    from . import conform as _conform
    from . import discover as _discover
    from . import proposals as _proposals

    entity = _load_or_exit(config)
    try:
        report = _conform.report(entity, campaign=campaign, campaign_dir=campaign_dir)
    except _discover.DiscoveryError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(EXIT_RUNTIME) from None
    for row in report.rows:
        typer.echo(_conform.format_row(row))

    # The to-do list is informational — it never changes the exit code (non-adoption
    # is legitimate, FR-021). Read-only and degrades to nothing off-repo (GH #14).
    if not no_proposals:
        try:
            trees = _discover.campaigns_roots(entity)
        except _discover.DiscoveryError:
            trees = ()
        for tree in trees:  # 005 — proposals are per-tree (FR-009); each degrades on its own
            try:
                todo = _proposals.list_proposals(tree, fetch=not no_fetch)
                for line in _proposals.format_todo(todo):
                    typer.echo(line)
            except _discover.DiscoveryError:
                pass

    raise typer.Exit(report.exit_code(strict=strict))


@app.command()
def render(
    campaign: str = typer.Argument(..., help="Campaign name"),
    campaign_dir: str = _dir_opt,
    check: bool = typer.Option(False, "--check", help="Report coherence only; write nothing"),
    config: str = _config_opt,
) -> None:
    """Regenerate (or --check) the derived wing files + .mempalaceignore from the authority."""
    from . import authority as _authority
    from . import discover as _discover
    from . import recipe as _recipe
    from . import render as _render

    entity = _load_or_exit(config)
    try:
        ref = _discover.resolve(entity, campaign, campaign_dir)
    except _discover.DiscoveryError as e:
        typer.echo(f"FAIL render: {e}", err=True)
        raise typer.Exit(EXIT_RUNTIME) from None
    if not ref.has_authority:
        typer.echo(
            f"{campaign}: no .mneme/mempalace.yaml authority (run `mneme mp bootstrap`)", err=True
        )
        raise typer.Exit(EXIT_RUNTIME)
    cfg_obj = _authority.load(ref.path)
    rec = _recipe.load(cfg_obj.recipe_version)
    if check:
        drifted = _render.coherent(cfg_obj, rec, ref.path)
        if drifted:
            for d in drifted:
                typer.echo(f"STALE-RENDER {campaign}: {d}")
            raise typer.Exit(EXIT_RUNTIME)
        typer.echo(f"{campaign}: derived files coherent with authority")
        raise typer.Exit(EXIT_OK)
    written = _render.write_all(cfg_obj, rec, ref.path)
    for w in written:
        typer.echo(f"rendered {w.relative_to(ref.path)}")


# ── publish / adopt (US3) ─────────────────────────────────────────────────────


@app.command()
def publish(
    recipe_version: str = typer.Option(None, "--recipe", help="Recipe version to publish"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview per campaign; write nothing"),
    config: str = _config_opt,
) -> None:
    """Stage a recipe upgrade for every campaign on a proposal branch (not the active checkout)."""
    from . import publish as _publish
    from .workcopy import WorkingCopyError

    entity = _load_or_exit(config)
    if dry_run:
        for plan in _publish.preview(entity):
            typer.echo(plan.line())
        raise typer.Exit(EXIT_OK)
    try:
        branch, plans = _publish.publish(entity, recipe_version=recipe_version)
    except WorkingCopyError as e:
        typer.echo(f"FAIL publish: {e}", err=True)
        raise typer.Exit(EXIT_RUNTIME) from None
    for plan in plans:
        typer.echo(plan.line())
    typer.echo(f"published proposal branch: {branch} (adopt per campaign to take it)")


@app.command()
def adopt(
    campaign: str = typer.Argument(..., help="Campaign to adopt the current recipe for"),
    here: bool = typer.Option(
        False, "--here", help="Write into the active checkout (uncommitted) instead of a branch"
    ),
    confirm: bool = typer.Option(False, "--confirm", help="Required with --here to actually write"),
    config: str = _config_opt,
) -> None:
    """Campaign-side gate: stage the upgrade on a branch (default), or --here to write it
    directly into the active checkout for review (FR-021/FR-030)."""
    from . import publish as _publish
    from .workcopy import WorkingCopyError

    entity = _load_or_exit(config)
    if here:
        # Interactive in-place adopt (FR-030): preview unless --confirm.
        ref_diff = _publish._discover.find(entity, campaign)
        if not ref_diff.has_authority:
            typer.echo(f"{campaign}: no authority — bootstrap first", err=True)
            raise typer.Exit(EXIT_RUNTIME)
        if not confirm:
            typer.echo(f"PREVIEW {campaign}: would write the upgraded authority + renders into")
            typer.echo("  the active checkout (mneme files only). Re-run with --confirm to apply.")
            raise typer.Exit(EXIT_OK)
        try:
            written, _ = _publish.adopt_in_place(entity, campaign)
        except WorkingCopyError as e:
            typer.echo(f"FAIL adopt: {e}", err=True)
            raise typer.Exit(EXIT_RUNTIME) from None
        for w in written:
            typer.echo(f"wrote {w.relative_to(ref_diff.path)}")
        typer.echo(f"adopted '{campaign}' into the active checkout — review and commit")
        raise typer.Exit(EXIT_OK)
    try:
        branch = _publish.adopt(entity, campaign)
    except WorkingCopyError as e:
        typer.echo(f"FAIL adopt: {e}", err=True)
        raise typer.Exit(EXIT_RUNTIME) from None
    typer.echo(f"staged adoption for '{campaign}' on branch: {branch} (merge/pull to take it)")


# ── migrate / mcp (US5) ───────────────────────────────────────────────────────


@app.command()
def migrate(
    campaign: str = typer.Argument(..., help="Campaign to migrate"),
    plan: str = typer.Option(..., "--plan", help="Path to the approved migration plan JSON"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate + show steps; apply nothing"),
    config: str = _config_opt,
) -> None:
    """Execute a human-approved migration plan in the working copy (verbatim, then verify)."""
    import json
    from pathlib import Path

    from . import migrate as _migrate
    from . import publish as _publish
    from .models import MigrationPlan, MigrationStep

    entity = _load_or_exit(config)
    raw = json.loads(Path(plan).read_text())
    mplan = MigrationPlan(
        campaign=raw.get("campaign", campaign),
        steps=tuple(
            MigrationStep(op=s["op"], args=s.get("args", {})) for s in raw.get("steps", [])
        ),
        approved_by_human=bool(raw.get("approved_by_human", False)),
    )
    problems = _migrate.validate_plan(mplan)
    if problems:
        for p in problems:
            typer.echo(f"REFUSED: {p}", err=True)
        raise typer.Exit(EXIT_RUNTIME)
    if dry_run:
        for step in mplan.steps:
            typer.echo(f"PLAN {step.op} {step.args}")
        raise typer.Exit(EXIT_OK)
    try:
        wc = _publish._clone_workcopy(entity, None, None)
        result = _migrate.migrate_in_dir(mplan, wc.path / campaign)
    except Exception as e:  # noqa: BLE001 - report any failure and exit non-zero
        typer.echo(f"FAIL migrate: {e}", err=True)
        raise typer.Exit(EXIT_RUNTIME) from None
    for step in result.executed:
        typer.echo(f"applied {step}")
    typer.echo(result.note)
    raise typer.Exit(EXIT_OK if result.conformant else EXIT_RUNTIME)


@app.command()
def mcp(config: str = _config_opt) -> None:
    """Run the advisory MCP server (read-only: target config, status, inventory, instructions)."""
    from mneme.mcp import server as _server

    entity = _load_or_exit(config)
    _server.run(entity)


# ── bootstrap (US4) ───────────────────────────────────────────────────────────


@app.command()
def bootstrap(
    campaign: str = typer.Argument(..., help="Campaign to bootstrap a mempalace authority for"),
    consolidate: bool = typer.Option(
        False, "--consolidate", help="Fold existing scattered wing configs into one authority"
    ),
    config: str = _config_opt,
) -> None:
    """Write a starter (or consolidated) authority into a campaign via the working copy."""
    from . import bootstrap as _bootstrap
    from .workcopy import WorkingCopyError

    entity = _load_or_exit(config)
    try:
        branch = _bootstrap.bootstrap(entity, campaign, consolidate=consolidate)
    except WorkingCopyError as e:
        typer.echo(f"FAIL bootstrap: {e}", err=True)
        raise typer.Exit(EXIT_RUNTIME) from None
    typer.echo(f"bootstrapped '{campaign}' on branch: {branch} (merge/pull to take it)")


# ── bringup (US1, 003) ────────────────────────────────────────────────────────


@app.command()
def bringup(
    campaign: str = typer.Argument(..., help="New campaign to bring up (greenfield)"),
    campaign_dir: str = _dir_opt,
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the steps; provision/mine nothing"),
    no_backup: bool = typer.Option(False, "--no-backup", help="Skip the bindings backup step"),
    config: str = _config_opt,
) -> None:
    """Bring up a new campaign: configure → render faces → provision → first-mine → back up."""
    from . import bringup as _bringup
    from . import discover as _discover

    entity = _load_or_exit(config)
    try:
        report = _bringup.bringup(
            entity, campaign, do_backup=not no_backup, dry_run=dry_run, campaign_dir=campaign_dir
        )
    except _discover.DiscoveryError as e:
        typer.echo(f"FAIL bringup: {e}", err=True)
        raise typer.Exit(EXIT_RUNTIME) from None
    for s in report.steps:
        flag = {"ok": "ok  ", "skipped": "skip", "failed": "FAIL"}.get(s.state, s.state)
        typer.echo(f"  {flag} {s.name:13} {s.observed or s.note}")
    for owed in report.owed:
        typer.echo(f"  TODO {owed}")
    if dry_run:
        outcome = "DRY-RUN: nothing changed"
    else:
        outcome = f"brought up {campaign}" if report.ready else f"NOT READY: {campaign}"
    typer.echo(outcome)
    raise typer.Exit(report.exit_code())


# ── backup / restore / regenerate (US3, 003) ─────────────────────────────────


@app.command()
def backup(
    campaign: str = typer.Argument(..., help="Campaign whose bindings to back up"),
    campaign_dir: str = _dir_opt,
    config: str = _config_opt,
) -> None:
    """Snapshot the bindings (store.sqlite3 + knowledge graph), excluding rebuildable/legacy."""
    from . import backup as _backup

    entity = _load_or_exit(config)
    try:
        b = _backup.backup(entity, campaign, campaign_dir=campaign_dir)
    except Exception as e:  # noqa: BLE001 - report any failure and exit non-zero
        typer.echo(f"FAIL backup: {e}", err=True)
        raise typer.Exit(EXIT_RUNTIME) from None
    typer.echo(f"backed up {campaign} bindings → {b.location} ({len(b.contents)} files)")


@app.command()
def restore(
    campaign: str = typer.Argument(..., help="Campaign to restore bindings into"),
    campaign_dir: str = _dir_opt,
    from_: str = typer.Option(None, "--from", help="A specific backup dir (default: latest)"),
    config: str = _config_opt,
) -> None:
    """Restore the bindings as-is — never re-embeds; turbovecdb rebuilds the index + auto-prunes."""
    from pathlib import Path

    from . import backup as _backup

    entity = _load_or_exit(config)
    try:
        restored = _backup.restore(
            entity, campaign, from_backup=Path(from_) if from_ else None, campaign_dir=campaign_dir
        )
    except _backup.BackupError as e:
        typer.echo(f"FAIL restore: {e}", err=True)
        raise typer.Exit(EXIT_RUNTIME) from None
    typer.echo(f"restored {len(restored)} binding files for {campaign} (no re-embed)")


@app.command()
def regenerate(
    campaign: str = typer.Argument(..., help="Campaign to re-embed from scratch"),
    campaign_dir: str = _dir_opt,
    confirm: bool = typer.Option(False, "--confirm", help="Required — re-embedding is expensive"),
    config: str = _config_opt,
) -> None:
    """Re-embed from scratch (the ONLY re-embed path): clears the store and first-mines."""
    from . import backup as _backup
    from . import discover as _discover

    if not confirm:
        typer.echo("regenerate re-embeds the whole campaign (expensive). Re-run with --confirm.")
        raise typer.Exit(EXIT_OK)
    entity = _load_or_exit(config)
    try:
        store, mined = _backup.regenerate(entity, campaign, campaign_dir=campaign_dir)
    except _discover.DiscoveryError as e:
        typer.echo(f"FAIL regenerate: {e}", err=True)
        raise typer.Exit(EXIT_RUNTIME) from None
    typer.echo(f"regenerated {campaign} → {store} (mined: {', '.join(mined) or 'nothing'})")


# ── faces (H1, GH #24) ────────────────────────────────────────────────────────


@app.command()
def faces(
    campaign: str = typer.Argument(..., help="Existing campaign to re-render all 4 faces for"),
    campaign_dir: str = _dir_opt,
    config: str = _config_opt,
) -> None:
    """Re-render the four faces (cli/cg_search/global_alias/mcp) from an existing authority."""
    from . import bringup as _bringup
    from . import discover as _discover
    from .authority import AuthorityError

    entity = _load_or_exit(config)
    try:
        written = _bringup.render_existing_faces(entity, campaign, campaign_dir=campaign_dir)
    except (AuthorityError,) as e:
        typer.echo(f"FAIL faces: {'; '.join(e.problems)}", err=True)
        raise typer.Exit(EXIT_RUNTIME) from None
    except _discover.DiscoveryError as e:
        typer.echo(f"FAIL faces: {e}", err=True)
        raise typer.Exit(EXIT_RUNTIME) from None
    for w in written:
        typer.echo(f"rendered {w}")


# ── drop-legacy (H2, GH #24) ──────────────────────────────────────────────────


@app.command(name="drop-legacy")
def drop_legacy(
    campaign: str = typer.Argument(..., help="Campaign whose store's chroma legacy to remove"),
    campaign_dir: str = _dir_opt,
    confirm: bool = typer.Option(False, "--confirm", help="Required — deletes the legacy files"),
    config: str = _config_opt,
) -> None:
    """Remove the dead chroma legacy (sqlite + segments + marker) from a campaign's store."""
    from . import authority as _authority
    from . import discover as _discover
    from . import health as _health

    entity = _load_or_exit(config)
    try:
        ref = _discover.resolve(entity, campaign, campaign_dir)
    except _discover.DiscoveryError as e:
        typer.echo(f"FAIL drop-legacy: {e}", err=True)
        raise typer.Exit(EXIT_RUNTIME) from None
    if not _authority.has_authority(ref.path):
        typer.echo(f"{campaign}: no authority — bootstrap/bringup first", err=True)
        raise typer.Exit(EXIT_RUNTIME)
    store = _authority.require_store(_authority.load(ref.path))
    found = _health.inspect(store.path).legacy_files
    if not found:
        typer.echo(f"{campaign}: no chroma legacy at {store.path}")
        raise typer.Exit(EXIT_OK)
    if not confirm:
        typer.echo(f"{campaign}: would remove {len(found)} legacy item(s) from {store.path}:")
        for p in found:
            typer.echo(f"  - {p.name}")
        typer.echo("Re-run with --confirm to delete.")
        raise typer.Exit(EXIT_OK)
    removed = _health.drop_legacy(store.path)
    typer.echo(f"dropped {len(removed)} legacy item(s) from {store.path}")
