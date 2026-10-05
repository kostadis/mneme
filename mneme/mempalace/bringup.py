"""Orchestrate end-to-end bring-up of a new campaign's mempalace (003, US1).

configure (bootstrap the authority + store pointer) → render all faces from that one
authority → provision/first-mine the dedicated store → (backup) → honest report.
Greenfield only (the existing fleet is the migration's job, GH #24). Creation-time
writes go directly into the campaign workspace (FR-005); a *later* re-config goes
through the working copy (002). Idempotent; not-ready on a failed step (FR-008).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from hypostasis import config as _config
from hypostasis.models import ConfigEntity

from . import authority as _authority
from . import bootstrap as _bootstrap
from . import discover as _discover
from . import embedder_guard as _guard
from . import provision as _provision
from . import recipe as _recipe
from . import render as _render
from .models import BringUpReport, BringUpStep, StorePointer
from .runner import MempalaceError, MempalaceRunner


def default_config_json(mempalace_root: Path | None = None) -> Path:
    """The global alias registry mneme merges into — under THIS host's palace root (006)."""
    root = Path(mempalace_root) if mempalace_root else _authority.default_mempalace_root()
    return root / "config.json"


def _default_store(campaign: str, mempalace_root: Path | None = None) -> StorePointer:
    alias = _authority._normalize_wing_name(campaign) or campaign
    return StorePointer(alias=alias, path=_authority.store_path_for(alias, mempalace_root))


def _plan_config(campaign: str, campaign_dir: Path, recipe, mempalace_root: Path | None = None):
    """Compute the authority (bootstrap or load) + ensure a store pointer — NO write."""
    if _authority.has_authority(campaign_dir):
        cfg = _authority.load(campaign_dir, mempalace_root=mempalace_root)
        if cfg.store is None:
            cfg = replace(cfg, store=_default_store(campaign, mempalace_root))
    else:
        cfg = _bootstrap.starter_config(campaign, campaign_dir, recipe)
        cfg = replace(cfg, store=_default_store(campaign, mempalace_root))
    return cfg


def bringup(
    entity: ConfigEntity,
    campaign: str,
    *,
    recipe=None,
    runner: MempalaceRunner | None = None,
    config_json: Path | None = None,
    do_backup: bool = True,
    dry_run: bool = False,
    campaign_dir: str | None = None,
    verbose: bool = False,
    prober=None,
) -> BringUpReport:
    rec = recipe or _recipe.current()
    runner = runner or MempalaceRunner.for_entity(entity, stream=verbose)
    mp_root = _config.mempalace_root(entity)
    config_json = config_json or default_config_json(mp_root)
    ref = _discover.resolve(entity, campaign, campaign_dir)
    steps: list[BringUpStep] = []
    cfg = _plan_config(campaign, ref.path, rec, mp_root)  # in-memory; no write yet

    if dry_run:
        steps.append(
            BringUpStep("configure", "skipped", note=f"would configure; store={cfg.store.alias}")
        )
        for name in ("render_faces", "provision", "first_mine", "backup"):
            steps.append(BringUpStep(name, "skipped", note="dry-run"))
        return BringUpReport(campaign, tuple(steps))

    try:  # GH #26: guard BEFORE any write, so a refused bring-up leaves no file changes
        _guard.require_writable(entity, cfg.store.path, prober)
    except MempalaceError as e:
        steps.append(BringUpStep("configure", "skipped", note="nothing written: guard refused"))
        steps.append(BringUpStep("first_mine", "failed", note=str(e)))
        return BringUpReport(campaign, tuple(steps))

    _authority.write(cfg, ref.path)  # creation-time direct write (FR-005)
    steps.append(
        BringUpStep("configure", "ok", observed=f".mneme/mempalace.yaml; store={cfg.store.alias}")
    )
    _render.render_faces(cfg, rec, ref.path, config_json, entity.env)
    steps.append(BringUpStep("render_faces", "ok", observed="cli/cg_search/global_alias/mcp"))

    try:
        fm = _provision.first_mine(cfg, ref.path, runner, entity=entity, prober=prober)
        store_path, mined = fm
    except MempalaceError as e:
        steps.append(BringUpStep("first_mine", "failed", note=str(e)))
        warns = (e.record_warning,) if getattr(e, "record_warning", None) else ()
        return BringUpReport(  # not-ready (FR-008)
            campaign, tuple(steps), skips=tuple(getattr(e, "skips", ())), warnings=warns
        )
    steps.append(BringUpStep("provision", "ok", observed=str(store_path)))
    steps.append(
        BringUpStep("first_mine", "ok", observed=f"mined: {', '.join(mined) or 'nothing yet'}")
    )

    # Backup step is completed in US3 (backup.py); reported here so the contract is visible.
    if do_backup:
        steps.append(_backup_step(entity, campaign, ref.path))
    else:
        steps.append(BringUpStep("backup", "skipped", note="--no-backup"))

    return BringUpReport(campaign, tuple(steps), skips=tuple(fm.skips),
        warnings=(fm.record_warning,) if fm.record_warning else (),
    )


def render_existing_faces(
    entity: ConfigEntity,
    campaign: str,
    *,
    recipe=None,
    config_json: Path | None = None,
    campaign_dir: str | None = None,
) -> list[Path]:
    """H1 (GH #24): re-render ALL four faces for an EXISTING campaign from its authority —
    no bootstrap, no mining. Used by convergence to wire the store-naming faces (cli pointer,
    cg_search, global alias, MCP) onto a campaign that already has a `.mneme/mempalace.yaml`."""
    rec = recipe or _recipe.current()
    mp_root = _config.mempalace_root(entity)
    config_json = config_json or default_config_json(mp_root)
    ref = _discover.resolve(entity, campaign, campaign_dir)
    if not _authority.has_authority(ref.path):
        raise _authority.AuthorityError([f"{campaign}: no authority — bootstrap/bringup first"])
    cfg = _authority.load(ref.path, mempalace_root=mp_root)
    return _render.render_faces(cfg, rec, ref.path, config_json, entity.env)


def _backup_step(entity: ConfigEntity, campaign: str, campaign_dir: Path) -> BringUpStep:
    try:
        from . import backup as _backup  # US3
    except ImportError:
        return BringUpStep("backup", "skipped", note="backup not yet wired (US3)")
    if not hasattr(_backup, "backup"):
        return BringUpStep("backup", "skipped", note="backup not yet wired (US3)")
    try:
        # Pass the already-resolved workspace path (GH #27) — otherwise backup re-resolves
        # `campaign` by name, forcing a full fleet-wide discover() crawl across every tree
        # (very slow on big monorepo roots), which looks like a hang after first-mine.
        b = _backup.backup(entity, campaign, campaign_dir=str(campaign_dir))
        return BringUpStep("backup", "ok", observed=str(b.location))
    except Exception as e:  # noqa: BLE001 - report, don't crash bring-up
        return BringUpStep("backup", "failed", note=str(e))

