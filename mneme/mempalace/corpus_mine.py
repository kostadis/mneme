"""Mine a declared corpus into a campaign's store, kind by kind (feature 007, US1).

Shared by `refresh` and `provision.first_mine`. The corpus is re-resolved on every call
(never read back from the TOC snapshot), then each kind is mined as
`mine <root> --files-from <its resolved targets> --wing <kind>`, so nothing outside the
declaration can enter the palace. Before each kind's mine this module repairs the three
cases mempalace's own already-mined check (source_file + mtime, never wing or content)
would otherwise leave wrong:

- changed content (T021): the file's drawers are forgotten, so a same-mtime edit is re-mined;
- wrong wing (T022): drawers sitting under a wing other than the file's `mined_as`;
- re-pointed symlink (T023): the recorded target differs from today's.

Only files that are IN the corpus are ever forgotten; undeclared sources are left for prune.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from mneme.corpus import config as _cconfig
from mneme.corpus import resolve as _resolve
from mneme.corpus import toc as _toc

from . import corpus_record as _crec
from . import mine_record as _record
from .mine_report import SkipNotice, WingSkips
from .models import Recipe
from .runner import MempalaceError, MempalaceRunner, SourceRecord

TOO_OLD = "mempalace too old for corpus mining (needs `mine --files-from`, `sources`, `forget`)"


@dataclass
class CorpusMine:
    """What a corpus mine did (or, with ``dry_run``, would do)."""

    kinds: dict[str, list[str]] = field(default_factory=dict)  # kind -> targets handed over
    remined: list[str] = field(default_factory=list)  # declared paths forgotten for new content
    rehomed: list[str] = field(default_factory=list)  # declared paths moved to their wing
    replaced: list[str] = field(default_factory=list)  # declared paths whose symlink moved
    skips: WingSkips = ()
    record_warning: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def mined(self) -> list[str]:
        return [k for k, v in self.kinds.items() if v]

    def detail_lines(self) -> list[str]:
        out = [f"  {k}: {', '.join(v) or '(none)'}" for k, v in self.kinds.items()]
        if self.rehomed:
            out.append(f"  re-homed {len(self.rehomed)}: {', '.join(self.rehomed)}")
        if self.replaced:
            out.append(
                f"  replaced {len(self.replaced)} re-pointed files: {', '.join(self.replaced)}"
            )
        if self.remined:
            out.append(f"  re-mining {len(self.remined)} changed: {', '.join(self.remined)}")
        return out

    def summary(self) -> str:
        bits = []
        if self.rehomed:
            bits.append(f"re-homed {len(self.rehomed)}")
        if self.replaced:
            bits.append(f"replaced {len(self.replaced)} re-pointed files")
        return "; ".join(bits)


def _real(root: Path, rel: str) -> str:
    return os.path.realpath(root / rel)


def _skipped(target: str, notices: tuple[SkipNotice, ...]) -> bool:
    """Did mempalace report skipping ``target``? Its names are printed (and truncated to 50
    chars) by mempalace, so match on the path, its tail, or its truncated basename."""
    base = os.path.basename(target)
    for n in notices:
        name = n.name.strip()
        if name and (
            name == target or target.endswith("/" + name) or name == base[:50]
            or name == target[-50:]
        ):
            return True
    return False


def _by_real_path(sources: list[SourceRecord]) -> dict[str, list[SourceRecord]]:
    out: dict[str, list[SourceRecord]] = {}
    for s in sources:
        out.setdefault(os.path.realpath(s.source_file), []).append(s)
    return out


def mine_corpus(
    campaign_dir: Path,
    campaign: str,
    store: Path | None,
    runner: MempalaceRunner,
    recipe: Recipe,
    *,
    dry_run: bool = False,
) -> CorpusMine:
    """Mine the campaign's declared corpus into ``store``. Raises `MempalaceError` (with
    ``.skips`` / ``.record_warning`` set) when it cannot: old mempalace, an invalid
    declaration (nothing is mined), or a failed kind (the run stops; no clean record)."""
    campaign_dir = Path(campaign_dir)
    if not runner.supports_corpus():
        raise MempalaceError(TOO_OLD)
    try:
        cfg = _cconfig.load(campaign_dir, recipe)
    except _cconfig.CorpusConfigError as e:
        raise MempalaceError(str(e)) from None
    resolved = _resolve.resolve(cfg, campaign_dir, recipe)
    out = CorpusMine()

    def snapshot() -> None:  # FR-012: re-resolved above, never read; rewritten for inspection
        if dry_run:
            return
        try:
            _toc.write(campaign_dir, _toc.build(resolved, cfg, recipe))
        except OSError as e:
            out.warnings.append(f"WARN could not write the corpus TOC snapshot: {e}")

    if not resolved.valid:
        snapshot()
        why = "; ".join(f.line() for f in resolved.findings)
        raise MempalaceError(f"invalid corpus, nothing mined: {why}")

    try:
        _mine_kinds(campaign_dir, campaign, store, runner, cfg, resolved, out, dry_run)
    finally:
        snapshot()
    return out


def _mine_kinds(campaign_dir, campaign, store, runner, cfg, resolved, out: CorpusMine, dry_run):
    record = None
    if store is not None:
        try:
            record = _crec.read(store)
        except _crec.CorpusRecordError as e:
            out.warnings.append(f"WARN {e}; treating every file as unrecorded")
    known = dict(record.files) if record else {}
    sources = runner.sources(store)  # None = unknown: forget candidates are not narrowed
    by_real = _by_real_path(sources) if sources is not None else {}
    skips: list[tuple[str, SkipNotice]] = []
    mined_kinds: list[str] = []

    for kind, rk in resolved.kinds.items():
        files = [f for f in rk.files if f.minable and f.mined_as == kind]
        targets = resolved.mine_targets(kind)
        out.kinds[kind] = targets
        if not targets:
            if store is not None and not dry_run:
                out.record_warning = out.record_warning or _crec.try_merge_kind(
                    store, campaign, cfg.corpus_sha256, kind, {}
                )
            continue

        forget_all: list[str] = []  # sources to drop whatever their wing
        wrong: dict[str, list[str]] = {}  # wing -> raw source_files held under a wrong wing
        for f in files:
            rec = known.get(f.path)
            now_real = _real(campaign_dir, f.mined_path)
            held = by_real.get(now_real, []) if sources is not None else None
            # T023: a symlink that was re-pointed since the last mine
            if rec and rec.get("target") and rec["target"] != f.mined_path:
                old_real = _real(campaign_dir, rec["target"])
                forget_all.append(str(campaign_dir / rec["target"]))
                if old_real != str(campaign_dir / rec["target"]):
                    forget_all.append(old_real)
                forget_all.extend(s.source_file for s in by_real.get(old_real, []))
                out.replaced.append(f.path)
            # T021: content changed since the recorded mine (or never recorded)
            elif not rec or rec.get("sha256") != f.sha256:
                if held is None:
                    forget_all += [str(campaign_dir / f.mined_path), now_real]
                    out.remined.append(f.path)
                elif held:
                    forget_all.extend(s.source_file for s in held)
                    out.remined.append(f.path)
            # T022: drawers under a wing that is not this file's mining kind
            if held:
                for s in held:
                    if s.wing != kind:
                        wrong.setdefault(s.wing, []).append(s.source_file)
                        if f.path not in out.rehomed:
                            out.rehomed.append(f.path)
        if dry_run:
            continue

        try:
            for wing, paths in wrong.items():
                runner.forget(sorted(set(paths)), palace=store, apply=True, wing=wing)
            if forget_all:
                runner.forget(sorted(set(forget_all)), palace=store, apply=True)
            res = runner.mine_files(campaign_dir, targets, wing=kind, palace=store)
        except MempalaceError as e:
            e.skips = tuple(skips)
            if store is not None:  # earlier kinds' skips are real; no stale clean record
                e.record_warning = _record.try_write(
                    store, campaign, mined_kinds, tuple(skips), status="failed", error=str(e)
                )
            raise
        notices = tuple(getattr(res, "skips", None) or ())
        skips.extend((kind, n) for n in notices)
        mined_kinds.append(kind)
        if store is not None:
            entries = {
                f.path: {"kind": kind, "sha256": f.sha256, "target": f.mined_path}
                for f in files if not _skipped(f.mined_path, notices)
            }
            out.record_warning = _crec.try_merge_kind(
                store, campaign, cfg.corpus_sha256, kind, entries
            ) or out.record_warning
    out.skips = tuple(skips)
    if store is not None and not dry_run:  # GH #31: remember the gaps for `mp status`
        out.record_warning = (
            _record.try_write(store, campaign, mined_kinds, out.skips) or out.record_warning
        )
