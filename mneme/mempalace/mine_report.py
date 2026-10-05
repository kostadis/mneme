"""Parse the files `mempalace mine` skipped (GH #31 — Principle I: a gap is never silent).

Pure text -> structured notices; no I/O. Handles BOTH mempalace output generations
(the older pinned `produced N chunks (> 500); add to SKIP_FILENAMES` on stdout and the
current `kostadis-dev` stderr formats) because the caller concatenates stdout + stderr.
Names are mempalace's own 50-char truncation (padding stripped) — never re-derived.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

KINDS = (
    "chunk_cap", "purge_failed", "symlink", "not_regular", "too_large", "stat_error", "other",
)

_CHUNK_RE = re.compile(
    r"^\s*!\s*\[skip\]\s+(?P<name>.*?)\s+produced\s+(?P<n>\d+)\s+chunks\s+"
    r"\(>\s*(?P<cap>\d+)\)(?P<rest>.*)$"
)
_PURGE_RE = re.compile(
    r"^\s*!\s*\[skip\]\s+(?:(?P<name>.*?)\s+)?stale-drawer purge failed"
    r"(?:\s+for\s+(?P<src>.+?))?\s+\((?P<exc>.*?)\);\s*leaving existing drawers untouched"
)
# Exact emitters (current kostadis-dev): miner.py:2312 / convo_miner.py:626 (symlink),
# miner.py:2330 / convo_miner.py:642 (not a regular file), miner.py:2337-2338 /
# convo_miner.py:649-650 (`(X.X MB) exceeds N MB limit`), miner.py:2349 / convo_miner.py:659
# (stat error). The 46fcfc2 pin has no `SKIP:` lines at all.
_SKIP_RE = re.compile(
    r"^\s*SKIP:\s+(?P<name>.+?)\s+\("
    r"(?P<why>symlink|not a regular file|(?P<mb>[\d.]+) MB|stat error: .*?)\)"
    r"(?P<tail>\s+exceeds\s+(?P<limit>\d+)\s+MB\s+limit)?\s*$"
)
_SUMMARY_RE = re.compile(r"^\s*Files skipped \(chunk cap (?P<cap>\d+)\):\s+(?P<k>\d+)")


@dataclass(frozen=True)
class SkipNotice:
    """One file mempalace declined to index. ``name`` is as printed (truncated to 50)."""

    name: str
    kind: str
    detail: str
    line: str


def _skip_kind(why: str, limit: str | None = None) -> tuple[str, str]:
    if why == "symlink":
        return "symlink", "symlink (not followed)"
    if why == "not a regular file":
        return "not_regular", "not a regular file"
    if why.startswith("stat error"):
        return "stat_error", why
    if re.fullmatch(r"[\d.]+ MB", why):
        over = f"over the {limit} MB limit" if limit else "over the size limit"
        return "too_large", f"{why}, {over}"
    return "other", why


def parse_skips(text: str) -> list[SkipNotice]:
    """Every skip named in ``text`` (mine stdout + stderr). Garbage yields nothing."""
    out: list[SkipNotice] = []
    summary_k = 0
    for raw in (text or "").splitlines():
        line = raw.rstrip()
        if (m := _CHUNK_RE.match(line)) is not None:
            detail = f"produced {m['n']} chunks (> {m['cap']} cap)"
            out.append(SkipNotice(m["name"].strip(), "chunk_cap", detail, line.strip()))
        elif (m := _PURGE_RE.match(line)) is not None:
            name = (m["name"] or m["src"] or "?").strip().strip("'\"")
            detail = f"stale-drawer purge failed ({m['exc']}); old drawers left, retried next mine"
            out.append(SkipNotice(name, "purge_failed", detail, line.strip()))
        elif (m := _SKIP_RE.match(line)) is not None:
            kind, detail = _skip_kind(m["why"], m["limit"])
            out.append(SkipNotice(m["name"].strip(), kind, detail, line.strip()))
        elif (m := _SUMMARY_RE.match(line)) is not None:
            summary_k += int(m["k"])
    named = sum(1 for s in out if s.kind == "chunk_cap")
    if summary_k > named:
        detail = (
            f"{summary_k} file(s) were skipped by the chunk cap but only {named} were named"
        )
        out.append(SkipNotice("(unnamed files)", "other", detail, f"Files skipped: {summary_k}"))
    return out


CHUNK_CAP_HINT = (
    "raise MEMPALACE_MAX_CHUNKS_PER_FILE in hypostasis.yaml env:, or split the file"
)

WingSkips = tuple[tuple[str, SkipNotice], ...]  # (wing, notice) pairs, in mine order


def warning_lines(campaign: str, skips: WingSkips) -> list[str]:
    """One `WARN index gap` line per skip, plus one hint per kind that has a known remedy."""
    lines = [
        f"WARN index gap: {campaign}/{wing}: {n.name} — {n.detail}" for wing, n in skips
    ]
    if any(n.kind == "chunk_cap" for _, n in skips):
        lines.append(f"  hint: {CHUNK_CAP_HINT}")
    return lines
