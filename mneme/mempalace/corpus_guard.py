"""Refusals for the wing-editing commands on a corpus campaign (007 US4, FR-001a, FR-019).

A corpus campaign declares what is mined in `.mneme/corpus.yaml` and has no wings, so any
command whose job is to write or reshape wings must say so and stop. Each refusal names the
command and the reason (T042).
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from mneme.corpus.config import CorpusConfigError, corpus_path
from mneme.corpus.config import parse as _parse_corpus

from .runner import MempalaceError


class CorpusRefusal(MempalaceError):
    """A wing-editing command met a corpus campaign."""


def refusal(command: str, campaign: str, reason: str) -> CorpusRefusal:
    return CorpusRefusal(
        f"`mneme mp {command}` refused for {campaign}: it is a corpus campaign "
        f"(.mneme/corpus.yaml declares what is mined, and it has no wings) — {reason}"
    )


def shadowed_kinds(campaign_dir: Path, recipe) -> list[str]:
    """Campaign kinds in this campaign's corpus.yaml whose names the ``recipe`` makes standard
    kinds. Adopting that recipe moves them to `kinds:` (see ``migrate_shadowed``). Unreadable
    YAML yields none (not this check's job; `mneme corpus check` reports it)."""
    try:
        raw = yaml.safe_load(corpus_path(campaign_dir).read_text()) or {}
    except (OSError, yaml.YAMLError):
        return []
    camp = raw.get("campaign_kinds") if isinstance(raw, dict) else None
    if not isinstance(camp, dict):
        return []
    standard = {k.name for k in recipe.kinds}
    return sorted(str(n) for n in camp if str(n) in standard)


class MoveRefused(Exception):
    """The campaign-kind move cannot be made. ``code`` is one of the MOVE_CODES; ``reason`` is
    one line."""

    def __init__(self, code: str, reason: str):
        super().__init__(f"{code}: {reason}")
        self.code, self.reason = code, reason


MOVE_CODES = ("shadowed-kind", "corpus-invalid", "corpus-hand-edit")

_TOP_KEY = re.compile(r"^([A-Za-z_][\w-]*)\s*:(.*)$")
_ANCHOR = re.compile(r"(^|[\s\[{,])[&*][\w-]+")


def _hand(reason: str) -> MoveRefused:
    return MoveRefused(
        "corpus-hand-edit",
        f"{reason}; move the declaration from `campaign_kinds:` to `kinds:` in "
        ".mneme/corpus.yaml by hand")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _is_filler(line: str) -> bool:
    return not line.strip() or line.lstrip().startswith("#")


def _top_keys(lines: list[str]) -> list[tuple[int, str, str]]:
    """``(line_index, key, rest_of_line)`` for each top-level mapping key."""
    out = []
    for i, ln in enumerate(lines):
        if ln[:1] in (" ", "#", "\n", "\r", "\t", "-") or not ln.strip():
            continue
        m = _TOP_KEY.match(ln.rstrip("\r\n"))
        if m:
            out.append((i, m.group(1), m.group(2)))
    return out


def _block(lines: list[str], key: str) -> tuple[int, int] | None:
    """``(key_line, end)``: the key's line and one past its last non-filler line."""
    keys = _top_keys(lines)
    for n, (i, k, rest) in enumerate(keys):
        if k != key:
            continue
        if rest.split("#")[0].strip():
            raise _hand(f"`{key}:` is not written as a block mapping")
        stop = keys[n + 1][0] if n + 1 < len(keys) else len(lines)
        end = i + 1
        for j in range(i + 1, stop):
            if not _is_filler(lines[j]):
                end = j + 1
        return i, end
    return None


def _entries(lines: list[str], key_line: int, end: int) -> list[tuple[str, int, int]]:
    """``(name, start, stop)`` of each child entry of the block; ``stop`` excludes trailing
    filler."""
    kids = [j for j in range(key_line + 1, end) if not _is_filler(lines[j])]
    if not kids:
        return []
    base = _indent(lines[kids[0]])
    starts = []
    for j in kids:
        if _indent(lines[j]) == base:
            m = re.match(r"^ *(?:\"([^\"]*)\"|'([^']*)'|([^\s:#'\"][^:#]*?))\s*:(\s|$)", lines[j])
            if not m:
                raise _hand("a `campaign_kinds:` entry has a layout this edit cannot read")
            starts.append((m.group(1) or m.group(2) or m.group(3), j))
    out = []
    for n, (name, j) in enumerate(starts):
        nxt = starts[n + 1][1] if n + 1 < len(starts) else end
        stop = j + 1
        for t in range(j + 1, nxt):
            if not _is_filler(lines[t]) or (lines[t].strip() and _indent(lines[t]) > base):
                stop = t + 1
        out.append((name, j, stop))
    return out


def _move_one(lines: list[str], name: str) -> list[str]:
    ck = _block(lines, "campaign_kinds")
    if ck is None:
        raise _hand("`campaign_kinds:` was not found")
    ents = _entries(lines, ck[0], ck[1])
    hit = [e for e in ents if e[0] == name]
    if len(hit) != 1:
        raise _hand(f"could not locate the `{name}` declaration")
    _, a, b = hit[0]
    base = _indent(lines[a])
    chunk = [ln if ln.endswith("\n") else ln + "\n" for ln in lines[a:b]]
    rest = lines[:a] + lines[b:]
    ck = _block(rest, "campaign_kinds")
    if not _entries(rest, ck[0], ck[1]):  # nothing left: drop the key (and its blank lines)
        stop = ck[1]
        if stop < len(rest) and not rest[stop].strip():
            stop += 1
        rest = rest[:ck[0]] + rest[stop:]
    kb = _block(rest, "kinds")
    if kb is None:
        cam = [i for i, k, _ in _top_keys(rest) if k == "campaign"]
        at = cam[0] + 1 if cam else 0
        if at and not rest[at - 1].endswith("\n"):
            rest[at - 1] += "\n"
        return rest[:at] + ["kinds:\n"] + chunk + rest[at:]
    kids = _entries(rest, kb[0], kb[1])
    target = _indent(rest[kids[0][1]]) if kids else base
    delta = target - base
    if delta > 0:
        chunk = [" " * delta + ln if ln.strip() else ln for ln in chunk]
    elif delta < 0:
        chunk = [ln[-delta:] if ln[:-delta].strip() == "" else ln.lstrip(" ") for ln in chunk]
    at = kb[1]
    if not rest[at - 1].endswith("\n"):
        rest[at - 1] += "\n"
    return rest[:at] + chunk + rest[at:]


def move_shadowed_text(campaign_dir: Path, recipe) -> tuple[str, list[str]] | None:
    """The new text of corpus.yaml after moving every campaign kind the ``recipe`` makes
    standard from `campaign_kinds:` to the end of `kinds:`, as a targeted text edit: the moved
    declaration is copied verbatim (comments, flow lists and an explicit trust included) and
    the rest of the file is untouched. ``None`` when nothing moves. Writes nothing.

    Raises MoveRefused when the name is already under `kinds:`, the layout is one the text edit
    cannot handle safely, or the result does not validate against ``recipe``."""
    moved = shadowed_kinds(campaign_dir, recipe)
    if not moved:
        return None
    text = corpus_path(campaign_dir).read_text()
    raw = yaml.safe_load(text)
    kinds = raw.get("kinds")
    if kinds is not None and not isinstance(kinds, dict):
        raise _hand("`kinds:` is not a mapping")
    for n in moved:
        if n in (kinds or {}):
            raise MoveRefused(
                "shadowed-kind",
                f"'{n}' is declared under both `kinds:` and `campaign_kinds:`")
    if text.startswith("---") or "\n---" in text or "\t" in text or _ANCHOR.search(text):
        raise _hand("the file uses document markers, tabs, anchors or aliases")
    lines = text.splitlines(keepends=True)
    try:
        for n in moved:
            lines = _move_one(lines, n)
    except MoveRefused:
        raise
    except (IndexError, TypeError) as e:  # a layout the scanner mis-read
        raise _hand("the file's layout is not one this edit can handle") from e
    new = "".join(lines)
    expected_kinds = {**(kinds or {}), **{n: raw["campaign_kinds"][n] for n in moved}}
    expected_camp = {k: v for k, v in raw["campaign_kinds"].items() if k not in moved}
    expected = {k: v for k, v in raw.items() if k not in ("kinds", "campaign_kinds")}
    expected["kinds"] = expected_kinds
    if expected_camp:
        expected["campaign_kinds"] = expected_camp
    try:
        got = yaml.safe_load(new)
    except yaml.YAMLError:
        got = None
    if got != expected:
        raise _hand("the edited file did not round-trip to the intended declaration")
    try:
        _parse_corpus(new.encode(), recipe, campaign_dir)
    except CorpusConfigError as e:
        why = "; ".join(f"{f.code}: {f.detail}" for f in e.findings) or str(e)
        raise MoveRefused(
            "corpus-invalid",
            f"corpus.yaml would not validate under recipe {recipe.version} after the move "
            f"({' '.join(why.split())})") from e
    return new, moved


def migrate_shadowed(
    command: str, campaign: str, campaign_dir: Path, recipe,
) -> tuple[str, list[str]] | None:
    """``move_shadowed_text`` as a command refusal (CorpusRefusal): nothing was written."""
    try:
        return move_shadowed_text(campaign_dir, recipe)
    except MoveRefused as e:
        raise refusal(command, campaign, f"{e}; nothing was written") from e
