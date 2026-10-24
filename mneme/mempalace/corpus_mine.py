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
from .mine_report import KINDS, SkipNotice, WingSkips
from .models import Recipe
from .runner import (
    ListedSkip,
    MempalaceError,
    MempalaceRunner,
    SourceRecord,
    holds_no_palace,
)


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


def _skipped(root: Path, target: str, listed: dict[str, ListedSkip]) -> bool:
    """Did mempalace report skipping ``target`` (relative to ``root``, the mine dir)? Exact:
    its mined path is in the `--skips-json` list (matched after normalising, so `./a` == `a`)."""
    return _norm(root, target) in listed


def _norm(root: Path, rel: str) -> str:
    return os.path.normpath(os.path.join(root, rel))


# mempalace's `--skips-json` reason codes -> mine_report.KINDS (identity where they agree).
_REASON_KIND = {
    "purge_skipped": "purge_failed",
    **{k: k for k in KINDS if k != "other"},
}


def _as_notice(s: ListedSkip) -> SkipNotice:
    """A `--skips-json` entry in the shape the report/record code prints (path + reason). The
    kind is in mine_report's vocabulary (unknown code -> 'other'); the raw code stays in the
    detail whenever it differs from the kind."""
    kind = _REASON_KIND.get(s.reason, "other")
    detail = s.detail or s.reason
    if s.reason != kind:
        detail = f"{detail} [{s.reason}]"
    return SkipNotice(s.path, kind, detail, f"{s.path} ({s.reason}) {s.detail}".strip())


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
        raise MempalaceError(runner.too_old_message())
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
    # None = unknown: forget candidates are not narrowed. A store that does not exist yet (first
    # mine) holds nothing, and the real `sources`/`forget` refuse a missing palace.
    sources = runner.sources(store)
    if sources is None and store is not None and holds_no_palace(Path(store)):
        sources = []
    by_real = _by_real_path(sources) if sources is not None else {}
    # a re-pointed link's old target may still be a corpus file (another kind mines it): its
    # drawers then belong to that file's own checks and a blind forget would delete them
    in_corpus = {_real(campaign_dir, f.mined_path) for k in resolved.kinds.values()
                 for f in k.files}
    skips: list[tuple[str, SkipNotice]] = []
    mined_kinds: list[str] = []
    unknown_kinds: list[str] = []  # skip list unavailable: neither clean nor recorded

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
                if old_real not in in_corpus:
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
            listed = runner.mine_files(campaign_dir, targets, wing=kind, palace=store)
        except MempalaceError as e:
            e.skips = tuple(skips)
            if store is not None:  # earlier kinds' skips are real; no stale clean record
                e.record_warning = _record.try_write(
                    store, campaign, mined_kinds, tuple(skips), status="failed", error=str(e)
                )
            raise
        if listed is None:
            # unknown, never "nothing skipped": record none of this kind and leave its prior
            # record entries untouched (so a later re-point can still fire)
            unknown_kinds.append(kind)
            out.warnings.append(
                f"WARN mempalace gave no usable --skips-json for {kind}: cannot tell which "
                f"files it skipped, so none are recorded as mined"
            )
            continue
        notices = tuple(_as_notice(s) for s in listed)
        skips.extend((kind, n) for n in notices)
        # chunk_cap = mined but truncated: recorded (so status converges), still a reported gap
        skipped = {_norm(campaign_dir, s.path): s for s in listed if s.reason != "chunk_cap"}
        mined_kinds.append(kind)
        if store is not None:
            entries = {
                f.path: {"kind": kind, "sha256": f.sha256, "target": f.mined_path}
                for f in files
                if not _skipped(campaign_dir, f.mined_path, skipped)
            }
            out.record_warning = _crec.try_merge_kind(
                store, campaign, cfg.corpus_sha256, kind, entries
            ) or out.record_warning
    out.skips = tuple(skips)
    if store is not None and not dry_run:  # GH #31: remember the gaps for `mp status`
        # an unknown skip list is not "no gaps": status's gaps row treats a failed record as
        # unverified, so that is how it is recorded
        extra = {}
        if unknown_kinds:
            extra = {
                "status": "failed",
                "error": f"skip list unknown for {', '.join(unknown_kinds)} "
                "(mempalace gave no usable --skips-json)",
            }
        out.record_warning = (
            _record.try_write(store, campaign, mined_kinds, out.skips, **extra)
            or out.record_warning
        )
