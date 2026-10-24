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
from mneme.corpus import compare as _compare
from mneme.corpus import config as _cconfig
from mneme.corpus import resolve as _cresolve
from mneme.corpus.config import has_corpus

from . import authority as _authority
from . import backup as _backup
from . import conform as _conform
from . import discover as _discover
from . import former_wings as _former
from . import recipe as _recipe
from .runner import MempalaceError, MempalaceRunner, SourceRecord, SyncCheck, holds_no_palace


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
    include_former_canon: tuple[str, ...] = (),
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
    if holds_no_palace(Path(cfg.store.path)):
        raise _authority.AuthorityError(
            [f"store missing at {cfg.store.path} — nothing to prune (run `mneme mp bringup`)"]
        )
    runner = runner or MempalaceRunner.for_entity(entity, stream=verbose)
    if has_corpus(ref.path):  # 007: the corpus defines the set; the wing-model path is below
        return _prune_corpus(
            entity, ref, cfg, campaign, runner, campaign_dir=campaign_dir, confirm=confirm,
            expect=expect, backup=backup, emit=emit, include_former_canon=include_former_canon,
        )
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


# ── 007: corpus campaigns ─────────────────────────────────────────────────────


def _former_canon(
    store: Path, deletion: list[SourceRecord]
) -> dict[str, tuple[int, int]]:
    """FR-018a: wing -> (files, drawers) for each former-canon wing in the deletion set. With
    no readable record every wing holding a deletion-set source counts (fail closed)."""
    try:
        rec = _former.read(store)
    except _former.FormerWingsError:
        rec = None
    canon = rec.authoritative() if rec is not None else None
    out: dict[str, tuple[int, int]] = {}
    for s in deletion:
        if canon is None or s.wing in canon:
            files, drawers = out.get(s.wing, (0, 0))
            out[s.wing] = (files + 1, drawers + s.drawers)
    return out


def _prune_corpus(
    entity, ref, cfg, campaign, runner, *, campaign_dir, confirm, expect, backup, emit,
    include_former_canon,
) -> bool:
    """Preview / apply removal of drawers outside the corpus (FR-018, R4): the deletion set is
    `undeclared ∪ (missing − not_materialized)`, bound by `--expect N` drawers, backed up,
    removed with `forget`, and re-verified with `sources`."""
    store = cfg.store.path
    if not runner.supports_corpus_read():  # prune uses `sources` and `forget`, never mines
        raise MempalaceError(runner.read_too_old_message())
    try:
        rec = _recipe.load(cfg.recipe_version)
        ccfg = _cconfig.load(ref.path, rec)
    except (_recipe.RecipeError, _cconfig.CorpusConfigError) as e:
        raise MempalaceError(f"cannot prune: {e}") from None
    resolved = _cresolve.resolve(ccfg, ref.path, rec)
    if not resolved.valid:  # an unreliable declaration would mis-classify the palace
        why = "; ".join(f.line() for f in resolved.findings)
        raise MempalaceError(f"cannot prune: invalid corpus ({why})")

    def read_set() -> tuple[list[SourceRecord], list[SourceRecord], list[SourceRecord]]:
        srcs = runner.sources(store)
        if srcs is None:
            raise MempalaceError("cannot read the palace's drawer sources (`mempalace sources`)")
        deletion, spared = _compare.deletion_set(resolved, srcs, ref.path)
        return srcs, deletion, spared

    _all, deletion, spared = read_set()
    n = sum(s.drawers for s in deletion)
    if confirm and expect is not None and n != expect:
        raise PruneAbort(
            f"deletion set changed since preview ({expect} → {n}) — re-run the preview"
        )
    if spared:
        emit(f"{len(spared)} not-materialized source(s) are NOT touched by prune "
             "(declared, merely absent from this checkout)")
    if not deletion:
        emit(f"{campaign}: nothing to prune (no undeclared or missing-file drawers)")
        return True
    former = _former_canon(store, deletion)
    named = set(include_former_canon)
    unnamed = sorted(w for w in former if w not in named)
    emit(f"{campaign}: {'pruning' if confirm else 'would remove'} {n} drawers from "
         f"{len(deletion)} source(s) outside the corpus")
    if not confirm:
        for s in deletion:
            emit(f"  [{s.wing}] {s.source_file}  ({s.drawers})")
    if former:
        for w, (files, drawers) in sorted(former.items()):
            mark = "named" if w in named else "NEEDS --include-former-canon"
            emit(f"  former-canon wing '{w}': {files} file(s), {drawers} drawers ({mark})")
        if unnamed and not confirm:
            emit("these wings were authoritative before the corpus (or their history is "
                 "unknown); deleting them needs the GM to name each")
    if not confirm:
        flags = "".join(f" --include-former-canon {w}" for w in sorted(former))
        emit("preview only — to delete exactly this set, re-run: "
             f"`mneme mp prune {campaign} --confirm --expect {n}{flags}`")
        return True
    if unnamed:
        raise PruneAbort(
            "refusing: the deletion set holds former-canon drawers from "
            + ", ".join(f"'{w}'" for w in unnamed)
            + " — name each with --include-former-canon <wing> after reviewing the preview"
        )
    if backup:
        snap = _backup.backup(entity, campaign, campaign_dir=campaign_dir)  # abort on failure
        emit(f"backed up bindings → {snap.location}")
    else:
        emit("skipping backup (--no-backup)")
    by_wing: dict[str, list[str]] = {}
    for s in deletion:
        by_wing.setdefault(s.wing, []).append(s.source_file)
    removed = 0
    for wing, paths in sorted(by_wing.items()):  # exact (wing, source) pairs, as reported
        removed += runner.forget(paths, palace=store, apply=True, wing=wing).drawers
    emit(f"{campaign}: removed {removed} drawers")
    ok = True
    if removed > n:
        emit(f"FAIL prune: removed {removed} drawers but only {n} were approved in the preview")
        ok = False
    gone = {(s.wing, s.source_file) for s in deletion}
    after = runner.sources(store)
    if after is None:
        emit("FAIL prune: cannot verify — `mempalace sources` failed after the delete")
        return False
    left = [s for s in after if (s.wing, s.source_file) in gone]
    if left:
        emit(f"FAIL prune: {len(left)} deleted source(s) remain "
             f"({sum(s.drawers for s in left)} drawers) — run `mneme mp status {campaign}`")
        ok = False
    elif ok:
        emit(f"verified: none of the {len(deletion)} deleted sources remain for {campaign}")
    return ok
