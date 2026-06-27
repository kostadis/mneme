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

from hypostasis.models import ConfigEntity

from . import authority as _authority
from . import bootstrap as _bootstrap
from . import discover as _discover
from . import provision as _provision
from . import recipe as _recipe
from . import render as _render
from .models import BringUpReport, BringUpStep, StorePointer
from .runner import MempalaceError, MempalaceRunner


def default_config_json() -> Path:
    return Path.home() / ".mempalace" / "config.json"


def _default_store(campaign: str) -> StorePointer:
    alias = _authority._normalize_wing_name(campaign) or campaign
    return StorePointer(alias=alias, path=Path.home() / ".mempalace" / "palaces" / alias)


def _plan_config(campaign: str, campaign_dir: Path, recipe):
    """Compute the authority (bootstrap or load) + ensure a store pointer — NO write."""
    if _authority.has_authority(campaign_dir):
        cfg = _authority.load(campaign_dir)
        if cfg.store is None:
            cfg = replace(cfg, store=_default_store(campaign))
    else:
        cfg = _bootstrap.starter_config(campaign, campaign_dir, recipe)
        cfg = replace(cfg, store=_default_store(campaign))
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
) -> BringUpReport:
    rec = recipe or _recipe.current()
    runner = runner or MempalaceRunner.for_venv(_venv(entity))
    config_json = config_json or default_config_json()
    ref = _discover.find(entity, campaign)
    steps: list[BringUpStep] = []
    cfg = _plan_config(campaign, ref.path, rec)  # in-memory; no write yet

    if dry_run:
        steps.append(
            BringUpStep("configure", "skipped", note=f"would configure; store={cfg.store.alias}")
        )
        for name in ("render_faces", "provision", "first_mine", "backup"):
            steps.append(BringUpStep(name, "skipped", note="dry-run"))
        return BringUpReport(campaign, tuple(steps))

    _authority.write(cfg, ref.path)  # creation-time direct write (FR-005)
    steps.append(
        BringUpStep("configure", "ok", observed=f".mneme/mempalace.yaml; store={cfg.store.alias}")
    )
    _render.render_faces(cfg, rec, ref.path, config_json)
    steps.append(BringUpStep("render_faces", "ok", observed="cli/cg_search/global_alias/mcp"))

    try:
        store_path, mined = _provision.first_mine(cfg, ref.path, runner)
    except MempalaceError as e:
        steps.append(BringUpStep("first_mine", "failed", note=str(e)))
        return BringUpReport(campaign, tuple(steps))  # not-ready (FR-008)
    steps.append(BringUpStep("provision", "ok", observed=str(store_path)))
    steps.append(
        BringUpStep("first_mine", "ok", observed=f"mined: {', '.join(mined) or 'nothing yet'}")
    )

    # Backup step is completed in US3 (backup.py); reported here so the contract is visible.
    if do_backup:
        steps.append(_backup_step(entity, campaign, ref.path))
    else:
        steps.append(BringUpStep("backup", "skipped", note="--no-backup"))

    return BringUpReport(campaign, tuple(steps))


def render_existing_faces(
    entity: ConfigEntity,
    campaign: str,
    *,
    recipe=None,
    config_json: Path | None = None,
) -> list[Path]:
    """H1 (GH #24): re-render ALL four faces for an EXISTING campaign from its authority —
    no bootstrap, no mining. Used by convergence to wire the store-naming faces (cli pointer,
    cg_search, global alias, MCP) onto a campaign that already has a `.mneme/mempalace.yaml`."""
    rec = recipe or _recipe.current()
    config_json = config_json or default_config_json()
    ref = _discover.find(entity, campaign)
    if not _authority.has_authority(ref.path):
        raise _authority.AuthorityError([f"{campaign}: no authority — bootstrap/bringup first"])
    cfg = _authority.load(ref.path)
    return _render.render_faces(cfg, rec, ref.path, config_json)


def _backup_step(entity: ConfigEntity, campaign: str, campaign_dir: Path) -> BringUpStep:
    try:
        from . import backup as _backup  # US3
    except ImportError:
        return BringUpStep("backup", "skipped", note="backup not yet wired (US3)")
    if not hasattr(_backup, "backup"):
        return BringUpStep("backup", "skipped", note="backup not yet wired (US3)")
    try:
        b = _backup.backup(entity, campaign)
        return BringUpStep("backup", "ok", observed=str(b.location))
    except Exception as e:  # noqa: BLE001 - report, don't crash bring-up
        return BringUpStep("backup", "failed", note=str(e))


def _venv(entity: ConfigEntity):
    return entity.venv if entity.venv and str(entity.venv) != "." else None
