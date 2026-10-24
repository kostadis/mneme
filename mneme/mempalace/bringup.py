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
from mneme.corpus import config as _cconfig
from mneme.corpus import resolve as _cresolve

from . import authority as _authority
from . import bootstrap as _bootstrap
from . import discover as _discover
from . import embedder_guard as _guard
from . import former_wings as _former
from . import provision as _provision
from . import recipe as _recipe
from . import render as _render
from .models import BringUpReport, BringUpStep, CampaignMempalaceConfig, StorePointer
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
    elif _cconfig.has_corpus(campaign_dir):
        # 007: the corpus file declares the wings, so the authority carries none (FR-001a).
        # Its `campaign:` must equal corpus.yaml's (rule 1), so take the name from there.
        name = _corpus_campaign(campaign_dir) or campaign
        cfg = CampaignMempalaceConfig(
            campaign=name, recipe_version=recipe.version, wings=(),
            store=_default_store(name, mempalace_root),
        )
    else:
        cfg = _bootstrap.starter_config(campaign, campaign_dir, recipe)
        cfg = replace(cfg, store=_default_store(campaign, mempalace_root))
    return cfg


def _corpus_campaign(campaign_dir: Path) -> str | None:
    import yaml

    try:
        raw = yaml.safe_load(_cconfig.corpus_path(campaign_dir).read_text())
    except (OSError, yaml.YAMLError):
        return None
    name = str(raw.get("campaign") or "").strip() if isinstance(raw, dict) else ""
    return name or None


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

    resolved = None
    if _cconfig.has_corpus(ref.path):  # 007: an invalid declaration writes nothing (dry run too)
        try:
            vrec = _recipe.load(cfg.recipe_version)  # the recipe the authority carries
            ccfg = _cconfig.load(ref.path, vrec)
            resolved = _cresolve.resolve(ccfg, ref.path, vrec)  # the disk too, like regenerate
            why = "; ".join(f.line() for f in resolved.findings) if not resolved.valid else ""
        except (_recipe.RecipeError, _cconfig.CorpusConfigError) as e:
            why = str(e)
        if why:
            steps.append(BringUpStep("configure", "skipped", note="nothing written: bad corpus"))
            steps.append(BringUpStep("first_mine", "failed", note=why))
            return BringUpReport(campaign, tuple(steps))
        rec = vrec  # one recipe serves validation, render and first_mine

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
    store_existed = Path(cfg.store.path).is_dir()
    record_warning = None
    if _cconfig.has_corpus(ref.path) and not store_existed:
        # GM 2026-10-24: a store first built from the corpus holds no former wings — recorded
        # now, so a failed first mine (or a re-run) still leaves it. An EXISTING store (maybe
        # with old wings) is left alone, so prune stays fail-closed.
        record_warning = _former.try_record_empty(cfg.store.path, cfg.campaign)
    # the render re-resolves AFTER its own deletes/rewrites, so the TOC snapshot is current
    _render.render_faces(cfg, rec, ref.path, config_json, entity.env)
    steps.append(BringUpStep("render_faces", "ok", observed="cli/cg_search/global_alias/mcp"))

    try:
        fm = _provision.first_mine(cfg, ref.path, runner, entity=entity, prober=prober)
        store_path, mined = fm
    except MempalaceError as e:
        steps.append(BringUpStep("first_mine", "failed", note=str(e)))
        warns = tuple(
            w for w in (record_warning, getattr(e, "record_warning", None)) if w
        )
        return BringUpReport(  # not-ready (FR-008)
            campaign, tuple(steps), skips=tuple(getattr(e, "skips", ())), warnings=warns
        )
    record_warning = "; ".join(x for x in (record_warning, fm.record_warning) if x) or None
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
        warnings=(*fm.warnings, *((record_warning,) if record_warning else ())),
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

