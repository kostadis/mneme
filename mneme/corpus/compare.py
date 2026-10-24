"""Compare the palace's drawer sources with the resolved corpus (feature 007, US2, FR-014-018).

Pure: takes the fresh `ResolvedCorpus`, the `sources()` result (None = unknown), the
corpus mine record and the TOC snapshot check, and returns every finding with its counts and
files. Findings are not mutually exclusive (data-model § Corpus finding states). OK only when
there are none (FR-017); anything unverifiable is UNKNOWN, never OK. `not_materialized`
paths (sparse checkouts, R7) are never a finding and their drawers are never in the deletion
set. Display truncation lives in the callers; the data here is complete.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from mneme.mempalace.corpus_mine import _by_real_path, _real
from mneme.mempalace.corpus_record import CorpusRecord
from mneme.mempalace.runner import SourceRecord

from . import toc as _toc
from .resolve import ResolvedCorpus

# Finding codes, in the order they are reported (most fundamental first).
INVALID = "invalid"
UNKNOWN = "unknown"
MISSING = "missing"
UNDECLARED = "undeclared-drawers"
OUT_OF_SCOPE = "out-of-scope"
UNMINED = "unmined"
STALE = "stale"
WRONG_WING = "wrong-wing"
TOC_STALE = "toc-stale"
ORDER = (INVALID, UNKNOWN, MISSING, UNDECLARED, OUT_OF_SCOPE, UNMINED, STALE, WRONG_WING,
         TOC_STALE)


# What the GM can do about a file mempalace skipped, per its reason code. None = transient
# (a refresh retries it); anything else is a remedy that is NOT `mp refresh`.
_PATH_REMEDY = "{reason}: fix the path in .mneme/corpus.yaml"
_SKIP_REMEDY: dict[str, str] = {
    "too_short": "too short to index: add content (then `mneme mp refresh`) or undeclare it",
    "too_large": "too large for mempalace: split it or undeclare it",
    "excluded": "excluded by a mempalace.yaml exclude pattern: remove the pattern or "
    "undeclare it",
    "unsupported_ext": "not a file type mempalace reads: undeclare it",
    **{r: _PATH_REMEDY.format(reason=r)
       for r in ("symlink", "not_regular", "outside_dir", "missing")},
}


def skip_remedy(reason: str) -> str | None:
    """The remedy for a skip that `mneme mp refresh` alone can never fix; None when a refresh
    retries it (limit, write_failed, failed, purge_skipped, stat_error, unknown codes)."""
    return _SKIP_REMEDY.get(reason)


@dataclass(frozen=True)
class CorpusFinding:
    code: str
    files: tuple[str, ...] = ()  # campaign-relative files (or finding lines for invalid/unknown)
    drawers: int = 0
    remedy: str = ""
    detail: str = ""
    # UNMINED only: (file, mempalace skip reason) for the files the last mine skipped and whose
    # content has not changed since. `mp refresh` cannot fix those (see ``skip_remedy``).
    skipped: tuple[tuple[str, str], ...] = ()

    @property
    def count(self) -> int:
        return len(self.files)


@dataclass(frozen=True)
class CorpusFindings:
    findings: tuple[CorpusFinding, ...] = ()
    # The sources `mp prune` removes: undeclared ∪ (missing − not_materialized), exactly as
    # `sources()` reported them (absolute `source_file`, FR-018).
    deletion: tuple[SourceRecord, ...] = ()
    spared: tuple[SourceRecord, ...] = ()  # not-materialized sources, held and never pruned
    verified: bool = True  # False when nothing could be compared (invalid / sources unknown)

    @property
    def ok(self) -> bool:
        return not self.findings

    def get(self, code: str) -> CorpusFinding | None:
        return next((f for f in self.findings if f.code == code), None)

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(f.code for f in self.findings)


@dataclass
class _Sets:
    undeclared: list[SourceRecord] = field(default_factory=list)
    missing: list[SourceRecord] = field(default_factory=list)
    spared: list[SourceRecord] = field(default_factory=list)
    out_of_scope: list[SourceRecord] = field(default_factory=list)
    wrong: dict[str, list[SourceRecord]] = field(default_factory=dict)  # declared path -> copies
    held: dict[str, list[SourceRecord]] = field(default_factory=dict)  # declared path -> copies


def _under(real: str, prefix: str) -> bool:
    return real == prefix or real.startswith(prefix + os.sep)


def _under_any(real: str, prefixes: set[str]) -> bool:
    """``real`` is, or is under, one of ``prefixes``: a set lookup per ancestor, so the cost
    is the path depth, not the number of prefixes."""
    p = real
    while True:
        if p in prefixes:
            return True
        parent = os.path.dirname(p)
        if parent == p:
            return False
        p = parent


def classify(
    resolved: ResolvedCorpus, sources: list[SourceRecord], campaign_dir: Path
) -> _Sets:
    """Sort every source into declared / missing / not-materialized / undeclared /
    out-of-scope by the REAL path it points at (symlinks are mined as their target)."""
    root = Path(campaign_dir)
    real_root = os.path.realpath(root)
    # real path -> [(declared path, mined_as, minable)]: a symlink and its target (or two
    # links to one file) are distinct declared paths served by the same drawers
    declared: dict[str, list[tuple[str, str | None, bool]]] = {}
    for rk in resolved.kinds.values():
        for f in rk.files:
            ent = (f.path, f.mined_as, f.minable)
            lst = declared.setdefault(_real(root, f.mined_path), [])
            if ent not in lst:
                lst.append(ent)
    nm = {_real(root, p) for rk in resolved.kinds.values() for p in rk.not_materialized}
    miss = {_real(root, p) for rk in resolved.kinds.values() for p in rk.missing}
    out = _Sets()
    for real, group in sorted(_by_real_path(sources).items()):
        if not _under(real, real_root):
            out.out_of_scope.extend(group)
        elif real in declared:
            group_decl = declared[real]
            _, mined_as, minable = group_decl[0]  # resolve assigns both per real path
            if mined_as is None or not minable:
                continue  # a declared file mempalace cannot mine: not ours to judge
            for path, _, _ in group_decl:
                out.held.setdefault(path, []).extend(group)
            bad = [s for s in group if s.wing != mined_as]
            if bad:  # one real file, one wing finding
                out.wrong.setdefault(group_decl[0][0], []).extend(bad)
        elif _under_any(real, nm):
            out.spared.extend(group)
        elif _under_any(real, miss):
            out.missing.extend(group)
        else:
            out.undeclared.extend(group)
    return out


def deletion_set(
    resolved: ResolvedCorpus, sources: list[SourceRecord], campaign_dir: Path
) -> tuple[list[SourceRecord], list[SourceRecord]]:
    """(deletion set, spared not-materialized sources) for `mp prune` (R4, R7)."""
    c = classify(resolved, sources, campaign_dir)
    return sorted(c.undeclared + c.missing, key=lambda s: (s.source_file, s.wing)), c.spared


def _rel(root: Path, source_file: str) -> str:
    real_root = os.path.realpath(root)
    real = os.path.realpath(source_file)
    if _under(real, real_root):
        return os.path.relpath(real, real_root).replace(os.sep, "/")
    return source_file


def _drawers(srcs: list[SourceRecord]) -> int:
    return sum(s.drawers for s in srcs)


def compare(
    resolved: ResolvedCorpus,
    sources: list[SourceRecord] | None,
    record: CorpusRecord | None,
    toc_check: _toc.TocCheck,
    campaign_dir: Path,
    *,
    record_error: str | None = None,
    sources_error: str | None = None,
) -> CorpusFindings:
    """Every finding for one campaign. ``sources`` None means the palace could not be read
    (UNKNOWN); ``record_error`` means the corpus mine record exists but is unreadable
    (staleness is then UNKNOWN). ``record`` None with readable sources means nothing was
    recorded, so a held file's content cannot be vouched for (stale)."""
    root = Path(campaign_dir)
    found: list[CorpusFinding] = []

    if not resolved.valid:  # what is declared cannot be trusted, so nothing is compared
        found.append(CorpusFinding(
            INVALID, tuple(f.line() for f in resolved.findings),
            remedy="edit .mneme/corpus.yaml (`mneme corpus check`)",
        ))
        return CorpusFindings(tuple(found), verified=False)

    missing = sorted({p for rk in resolved.kinds.values() for p in rk.missing})
    unknown: list[str] = []
    deletion: list[SourceRecord] = []
    spared: list[SourceRecord] = []
    missing_drawers = 0
    if sources is None:
        unknown.append(sources_error or "the palace's drawer sources could not be read")
    else:
        c = classify(resolved, sources, root)
        deletion = sorted(c.undeclared + c.missing, key=lambda s: (s.source_file, s.wing))
        spared = c.spared
        missing_drawers = _drawers(c.missing)
        if c.undeclared:
            found.append(CorpusFinding(
                UNDECLARED, tuple(sorted({_rel(root, s.source_file) for s in c.undeclared})),
                _drawers(c.undeclared), "mneme mp prune",
            ))
        if c.out_of_scope:
            found.append(CorpusFinding(
                OUT_OF_SCOPE, tuple(sorted({s.source_file for s in c.out_of_scope})),
                _drawers(c.out_of_scope),
                "moved campaign or foreign store? `mneme mp regenerate --confirm`",
            ))
        mine = [f for rk in resolved.kinds.values() for f in rk.files
                if f.minable and f.mined_as == rk.name]
        unmined = sorted(f.path for f in mine if f.path not in c.held)
        if unmined:
            # the corpus record says why a file was skipped, but only for the content it saw:
            # a changed file is an ordinary unmined one that a refresh retries
            known_files = record.files if record else {}
            by_path = {f.path: f for f in mine}
            fixed: list[tuple[str, str]] = []
            changed: list[str] = []
            for p in unmined:
                r = known_files.get(p) or {}
                reason = r.get("skipped")
                if not reason:
                    continue
                if r.get("sha256") != by_path[p].sha256:
                    changed.append(f"{p} changed since it was skipped as {reason}; "
                                   "refresh to retry")
                elif skip_remedy(reason):
                    fixed.append((p, reason))
            found.append(CorpusFinding(
                UNMINED, tuple(unmined), remedy="mneme mp refresh",
                detail="; ".join(changed), skipped=tuple(fixed),
            ))
        if record_error is not None:
            unknown.append(f"the corpus mine record is unreadable ({record_error}); "
                           "staleness cannot be verified")
        else:
            known = record.files if record else {}
            stale = sorted(
                f.path for f in mine if f.path in c.held and not (
                    (r := known.get(f.path)) and r.get("sha256") == f.sha256
                    and r.get("target") in (None, f.mined_path)
                )
            )
            if stale:
                found.append(CorpusFinding(
                    STALE, tuple(stale), remedy="mneme mp refresh",
                    detail="" if record else "no corpus mine record: content cannot be vouched for",
                ))
        if c.wrong:
            found.append(CorpusFinding(
                WRONG_WING, tuple(sorted(c.wrong)),
                _drawers([s for g in c.wrong.values() for s in g]), "mneme mp refresh",
                detail="; ".join(
                    f"{p} in {', '.join(sorted({s.wing for s in g}))}"
                    for p, g in sorted(c.wrong.items())
                ),
            ))
    if missing:
        found.append(CorpusFinding(
            MISSING, tuple(missing), missing_drawers,
            "edit .mneme/corpus.yaml; `mneme mp prune` also drops its drawers",
        ))
    if unknown:
        found.append(CorpusFinding(
            UNKNOWN, tuple(unknown), remedy="check the store (`mneme mp status`)",
        ))
    if not toc_check.ok:
        why = ("no TOC snapshot yet" if toc_check.state == _toc.MISSING
               else "; ".join(toc_check.reasons) or "snapshot differs")
        found.append(CorpusFinding(TOC_STALE, (), remedy="mneme mp render", detail=why))

    found.sort(key=lambda f: ORDER.index(f.code))
    return CorpusFindings(tuple(found), tuple(deletion), tuple(spared), sources is not None)
