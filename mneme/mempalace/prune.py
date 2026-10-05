"""`mneme mp prune` — explicit, backed-up removal of orphaned drawers.

`refresh` only mines; it never deletes. Removing the drawers of deleted / now-gitignored
sources is a separate, reviewed step: preview by default, `--confirm` to act, a bindings
backup first (abort if it fails), then Principle I — re-verify with a fresh dry-run rather
than trust the apply. Out-of-scope drawers are never touched here (they need `regenerate`).
This is not a mine, so the GH #31 `mneme-last-mine.json` record is left alone.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from hypostasis import config as _config
from hypostasis.models import ConfigEntity

from . import authority as _authority
from . import backup as _backup
from . import conform as _conform
from . import discover as _discover
from .runner import MempalaceError, MempalaceRunner, SyncCheck


def _need_report(chk: SyncCheck, what: str) -> SyncCheck:
    """Unknown is not green (Principle I): an unparseable dry-run stops the prune."""
    if chk.stale is None:
        raise MempalaceError(f"cannot {what}: {chk.reason}")
    return chk


def _counts(chk: SyncCheck) -> str:
    return f"{chk.missing} missing, {chk.gitignored} gitignored"


class PruneAbort(Exception):
    """The prune stopped on purpose, before deleting anything (not an error in mempalace)."""


def _listed(chk: SyncCheck) -> int:
    """Drawers accounted for by the report's (top-N only) source list."""
    total = 0
    for ln in chk.top_sources:
        m = re.search(r"\((\d+)\)\s*$", ln)
        total += int(m.group(1)) if m else 0
    return total


def prune(
    entity: ConfigEntity,
    campaign: str,
    *,
    campaign_dir: str | None = None,
    confirm: bool = False,
    expect: int | None = None,
    backup: bool = True,
    verbose: bool = False,
    runner: MempalaceRunner | None = None,
    emit: Callable[[str], None] = print,
) -> bool:
    """Preview (default) or apply removal of this campaign's orphaned drawers.

    Lines go out through ``emit`` AS THEY HAPPEN, so the backup path is visible even if a
    later step raises. `--confirm` is bound to the reviewed preview: ``expect`` is the count
    the human saw, and a different fresh count aborts before any backup or deletion.
    Returns True iff the prune ended clean."""
    ref = _discover.resolve(entity, campaign, campaign_dir)
    cfg = _authority.load(ref.path, mempalace_root=_config.mempalace_root(entity))
    if cfg.store is None:
        raise _authority.AuthorityError(
            ["no store pointer — cannot prune an unknown palace (run `mneme mp bringup`)"]
        )
    if not Path(cfg.store.path).is_dir():
        raise _authority.AuthorityError(
            [f"store missing at {cfg.store.path} — nothing to prune (run `mneme mp bringup`)"]
        )
    runner = runner or MempalaceRunner.for_entity(entity, stream=verbose)
    palace, extra = _conform.sync_scope(ref, cfg)  # the SAME scope the status row checks

    before = _need_report(runner.sync(ref.path, palace, extra), "preview the prune")
    n = before.missing + before.gitignored
    if confirm and expect is not None and n != expect:
        raise PruneAbort(
            f"orphan set changed since preview ({expect} → {n}) — re-run the preview"
        )
    if n == 0:
        emit(f"{campaign}: nothing to prune (no missing or gitignored sources)")
        _note_out_of_scope(emit, campaign, before)
        return True
    if not confirm:
        emit(f"{campaign}: would remove {n} orphaned drawers ({_counts(before)})")
        for src in before.top_sources:
            emit(f"  {src}")
        if n > _listed(before):
            emit(
                f"  … and {n - _listed(before)} more drawers from sources mempalace did not list"
            )
        _note_out_of_scope(emit, campaign, before)
        emit(
            "preview only — to delete exactly this set, re-run: "
            f"`mneme mp prune {campaign} --confirm --expect {n}`"
        )
        return True

    emit(f"{campaign}: pruning {n} orphaned drawers ({_counts(before)})")
    if backup:
        snap = _backup.backup(entity, campaign, campaign_dir=campaign_dir)  # abort on failure
        emit(f"backed up bindings → {snap.location}")
    else:
        emit("skipping backup (--no-backup)")
    applied = runner.sync(ref.path, palace, extra, apply=True)
    removed = applied.missing + applied.gitignored
    emit(f"{campaign}: removed {removed} orphaned drawers ({_counts(applied)})")
    ok = True
    if removed > n:
        emit(f"FAIL prune: removed {removed} drawers but only {n} were approved in the preview")
        ok = False
    after = _need_report(runner.sync(ref.path, palace, extra), "verify the prune")
    emit(f"  before: {_counts(before)}  after: {_counts(after)}")
    _note_out_of_scope(emit, campaign, after)
    if after.missing + after.gitignored:
        emit(
            f"FAIL prune: {after.missing + after.gitignored} orphaned drawers remain "
            f"({_counts(after)}) — run `mneme mp status {campaign}`"
        )
        ok = False
    elif ok:
        emit(f"verified: no orphaned drawers remain for {campaign}")
    return ok


def _note_out_of_scope(emit: Callable[[str], None], campaign: str, chk: SyncCheck) -> None:
    if chk.out_of_scope:
        emit(
            f"{chk.out_of_scope} out-of-scope drawers are NOT touched by prune "
            f"(they need `mneme mp regenerate {campaign} --confirm`)"
        )
