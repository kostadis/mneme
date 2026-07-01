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
from pathlib import Path

from hypostasis import config as _config
from hypostasis.models import ConfigEntity

from . import authority as _authority
from . import discover as _discover
from . import health as _health
from . import provision as _provision
from .models import BindingsBackup
from .runner import MempalaceRunner

MARKER = ".mneme-backup"  # labels a backup dir as derived/disposable


class BackupError(Exception):
    """A backup/restore could not proceed."""


def backups_root(entity: ConfigEntity) -> Path:
    root = _config.single_root(entity, "backups")
    return root if root else Path.home() / ".mneme" / "backups"


def _store_path(entity: ConfigEntity, campaign: str) -> Path:
    ref = _discover.find(entity, campaign)
    cfg = _authority.load(ref.path)
    return _authority.require_store(cfg).path


def latest_backup(entity: ConfigEntity, campaign: str) -> Path | None:
    base = backups_root(entity) / campaign
    if not base.is_dir():
        return None
    snaps = sorted((p for p in base.iterdir() if (p / MARKER).is_file()), reverse=True)
    return snaps[0] if snaps else None


def has_backup(entity: ConfigEntity, campaign: str) -> bool:
    return latest_backup(entity, campaign) is not None


def backup(entity: ConfigEntity, campaign: str, *, stamp: str | None = None) -> BindingsBackup:
    """Snapshot the bindings to `<backups>/<campaign>/<stamp>/`, preserving layout."""
    store = _store_path(entity, campaign)
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


def restore(entity: ConfigEntity, campaign: str, *, from_backup: Path | None = None) -> list[Path]:
    """Copy the bindings back into the store — NEVER re-embeds. turbovecdb rebuilds the
    index from the restored bindings and prunes removed entries on next open (FR-012)."""
    src = Path(from_backup) if from_backup else latest_backup(entity, campaign)
    if src is None or not (src / MARKER).is_file():
        raise BackupError(f"{campaign}: no backup to restore from")
    store = _store_path(entity, campaign)
    store.mkdir(parents=True, exist_ok=True)
    restored: list[Path] = []
    for f in src.rglob("*"):
        if f.is_dir() or f.name == MARKER:
            continue
        rel = f.relative_to(src)
        out = store / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, out)
        restored.append(out)
    return restored  # no mine/embed invoked — bindings preserved


def regenerate(
    entity: ConfigEntity, campaign: str, *, runner: MempalaceRunner | None = None
) -> tuple[Path, list[str]]:
    """The ONLY re-embed path (FR-012): clear the store and first-mine from scratch."""
    ref = _discover.find(entity, campaign)
    cfg = _authority.load(ref.path)
    store = _authority.require_store(cfg).path
    if store.is_dir():
        shutil.rmtree(store)
    runner = runner or MempalaceRunner.for_venv(_venv(entity))
    return _provision.first_mine(cfg, ref.path, runner)


def _venv(entity: ConfigEntity):
    return entity.venv if entity.venv and str(entity.venv) != "." else None
