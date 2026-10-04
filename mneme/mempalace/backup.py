"""Bindings backup / restore / regenerate (003, US3, FR-011/012).

Backup **preserves the bindings** — the turbovec `store.sqlite3` files + knowledge graph
(the source of truth) — excluding the rebuildable `index.tvim` and the dead `chroma.sqlite3`.
Restore copies them back **as-is, never re-embedding**; turbovecdb rebuilds the index from the
bindings and auto-prunes removed entries on next open. Re-generation (re-embed) is the separate,
explicit `regenerate` verb. Backups are derived/disposable — never an authority (Principle IV).
"""

from __future__ import annotations

import datetime as _dt
import shutil
from dataclasses import dataclass
from pathlib import Path

from hypostasis import config as _config
from hypostasis.models import ConfigEntity

from . import authority as _authority
from . import discover as _discover
from . import embedder_guard as _guard
from . import health as _health
from . import mine_record as _mine_record
from . import provision as _provision
from .models import FAIL_STATES, BindingsBackup, ConformanceRow, State
from .runner import MempalaceRunner

MARKER = ".mneme-backup"  # labels a backup dir as derived/disposable


class BackupError(Exception):
    """A backup/restore could not proceed."""


def backups_root(entity: ConfigEntity) -> Path:
    root = _config.single_root(entity, "backups")
    return root if root else Path.home() / ".mneme" / "backups"


def _store_path(entity: ConfigEntity, campaign: str, campaign_dir: str | None = None) -> Path:
    ref = _discover.resolve(entity, campaign, campaign_dir)
    cfg = _authority.load(ref.path, mempalace_root=_config.mempalace_root(entity))
    return _authority.require_store(cfg).path


def latest_backup(entity: ConfigEntity, campaign: str) -> Path | None:
    base = backups_root(entity) / campaign
    if not base.is_dir():
        return None
    snaps = sorted((p for p in base.iterdir() if (p / MARKER).is_file()), reverse=True)
    return snaps[0] if snaps else None


def has_backup(entity: ConfigEntity, campaign: str) -> bool:
    return latest_backup(entity, campaign) is not None


def backup(
    entity: ConfigEntity, campaign: str, *, stamp: str | None = None, campaign_dir: str | None = None
) -> BindingsBackup:
    """Snapshot the bindings to `<backups>/<campaign>/<stamp>/`, preserving layout."""
    store = _store_path(entity, campaign, campaign_dir)
    ds = _health.inspect(store)
    if not ds.present:
        raise BackupError(f"{campaign}: no store to back up at {store}")
    stamp = stamp or _dt.datetime.now().strftime("%Y%m%d-%H%M%S")  # noqa: DTZ005 - local stamp
    dest = backups_root(entity) / campaign / stamp
    dest.mkdir(parents=True, exist_ok=True)
    contents: list[Path] = []
    for f in ds.bindings_files:  # store.sqlite3 (per collection) + knowledge_graph.sqlite3 ONLY
        rel = f.relative_to(store)
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, out)
        contents.append(out)
    (dest / MARKER).write_text("derived/disposable bindings snapshot — not an authority\n")
    return BindingsBackup(campaign=campaign, location=dest, taken=stamp, contents=tuple(contents))


@dataclass(frozen=True)
class RestoreResult:
    """GH #34 — what was copied and whether the restored index is verified fresh."""

    restored: list[Path]
    rows: list[ConformanceRow]
    fresh: bool
    previous_store: Path | None = None  # the replaced store, kept aside (never auto-deleted)
    missing: tuple[str, ...] = ()  # freshness dimensions that could not be evaluated


_FRESHNESS_DIMS = ("recipe", "render", "embedder", "index", "store")
_NOT_FRESH = (State.STALE, State.INDEX_UNVERIFIED)
# GH #31: the `gaps` row (INDEX_GAPS / no-record INDEX_UNVERIFIED) is deliberately NOT a
# freshness dimension: a restore replaces the store and never re-mines, so the restored store
# has no mine record by construction, and skipped files are a property of the sources, not of
# whether the restored bindings are stale. INDEX_GAPS is therefore not in _NOT_FRESH.


def _precheck_embedder(entity: ConfigEntity, campaign: str, src: Path, prober) -> None:
    """GH #34 — refuse a backup that is incoherent (collections disagree on dimension) or built
    at a DIFFERENT embedder dimension (restoring it would reinstate an unqueryable index).
    Unknown on either side never blocks: restore is a recovery tool, and the post-restore
    rows report what could not be verified (Principle I)."""
    dims = _guard.built_dimensions(src)
    known = {d for d in dims.values() if d is not None}
    if len(known) > 1:
        raise BackupError(
            f"{campaign}: backup collections disagree on embedding dimension ({dims}) — "
            f"incoherent backup; refusing to restore. Use an older backup, or run "
            f"`mneme mp regenerate {campaign} --confirm` to rebuild from scratch"
        )
    if len(known) != 1:
        return
    built = next(iter(known))
    expected = _guard.expected_dimension(entity, prober)
    if expected is not None and built != expected:
        raise BackupError(
            f"{campaign}: backup was built at embedding dim {built} but the current embedder "
            f"yields dim {expected} — restoring would reinstate an unqueryable index. Restore "
            f"the matching embedder in hypostasis.yaml env:, or run "
            f"`mneme mp regenerate {campaign} --confirm` to rebuild from scratch"
        )


def _aside_path(store: Path) -> Path:
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")  # noqa: DTZ005 - local stamp
    cand = store.with_name(f"{store.name}.pre-restore-{stamp}")
    n = 1
    while cand.exists():
        n += 1
        cand = store.with_name(f"{store.name}.pre-restore-{stamp}-{n}")
    return cand


def restore(
    entity: ConfigEntity,
    campaign: str,
    *,
    from_backup: Path | None = None,
    campaign_dir: str | None = None,
    runner: MempalaceRunner | None = None,
    prober=None,
) -> RestoreResult:
    """REPLACE the store with the backup's bindings — NEVER re-embeds. turbovecdb rebuilds the
    index from the restored bindings and prunes removed entries on next open (FR-012).
    GH #34: the index is a derived cache (Principle IV), so refuse an incoherent or
    embedder-mismatched backup before touching anything; move the existing store aside
    (reversible — rolled back if the copy fails, kept on success); then re-check the restored
    state with conform's own row builders and report clean vs stale (Principle I). Never
    auto re-mines — that is a human decision."""
    from . import conform as _conform

    src = Path(from_backup) if from_backup else latest_backup(entity, campaign)
    if src is None or not (src / MARKER).is_file():
        raise BackupError(f"{campaign}: no backup to restore from")
    store = _store_path(entity, campaign, campaign_dir)
    _precheck_embedder(entity, campaign, src, prober)  # BEFORE any rename
    # The derived store location may be a symlink to the real store (authority.store_path_for):
    # move aside / recreate / roll back on the TARGET so the symlink stays intact and keeps
    # pointing at the restored data (never rename the link itself).
    target = store.resolve()
    aside: Path | None = None
    if target.exists():
        aside = _aside_path(target)
        target.rename(aside)
    restored: list[Path] = []
    try:
        target.mkdir(parents=True, exist_ok=True)
        for f in src.rglob("*"):
            if f.is_dir() or f.name == MARKER:
                continue
            out = target / f.relative_to(src)
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, out)
            restored.append(out)
    except BaseException:
        shutil.rmtree(target, ignore_errors=True)
        if aside is not None:
            aside.rename(target)
        raise
    if aside is not None:  # GH #31: skips belong to the sources, which restore doesn't change
        stamp = aside.name.rsplit(".pre-restore-", 1)[-1]
        _mine_record.carry_over(aside, target, f"restore {stamp}")
    # no mine/embed invoked — bindings preserved; now observe, don't assume
    runner = runner or MempalaceRunner.for_entity(entity)
    # One resolved ref per call; with --dir its rows are named after the workspace dir, not the
    # `campaign` arg, so do NOT filter by name — filter by dimension only.
    rep = _conform.report(
        entity, campaign, campaign_dir=campaign_dir, runner=runner, prober=prober
    )
    rows = [r for r in rep.rows if r.dimension in _FRESHNESS_DIMS]
    missing = tuple(d for d in _FRESHNESS_DIMS if not any(r.dimension == d for r in rows))
    bad = any(
        r.state in FAIL_STATES or r.state in _NOT_FRESH
        or (r.dimension == "store" and r.state is not State.BUILT)
        for r in rows
    )
    return RestoreResult(
        restored=restored, rows=rows, fresh=not bad and not missing,
        previous_store=aside, missing=missing,
    )


def regenerate(
    entity: ConfigEntity,
    campaign: str,
    *,
    runner: MempalaceRunner | None = None,
    campaign_dir: str | None = None,
    verbose: bool = False,
    prober=None,
) -> tuple[Path, list[str]]:
    """The ONLY re-embed path (FR-012): clear the store and first-mine from scratch."""
    ref = _discover.resolve(entity, campaign, campaign_dir)
    cfg = _authority.load(ref.path, mempalace_root=_config.mempalace_root(entity))
    store = _authority.require_store(cfg).path
    # GH #26: verify the embedder answers BEFORE deleting — else a down endpoint leaves
    # the user with no store and a failed mine.
    _guard.require_embedder_answers(entity, prober)
    if store.is_dir():
        shutil.rmtree(store)
    runner = runner or MempalaceRunner.for_entity(entity, stream=verbose)
    # store was just cleared ⇒ the GH #26 guard sees EMPTY and allows (this IS the remedy).
    return _provision.first_mine(cfg, ref.path, runner, entity=entity, prober=prober)

