"""Load + validate the consumer inventory (`mneme/recipes/consumers.yaml`, feature 007, FR-023).

The file is the GM's reviewed record (`contracts/consumers-yaml.md`). Loading reports ALL
problems at once, each naming the entry and the field. mneme never infers a classification.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from mneme.mempalace import recipe as _recipe

DEFAULT = Path(__file__).resolve().parent.parent / "recipes" / "consumers.yaml"
SCHEMA = 1
MODES = ("palace", "toc", "partial", "independent")
_REQUIRED = ("name", "repo", "entry", "kinds", "mode")
_OPTIONAL = ("via", "reads", "kinds_toc", "other", "note", "issue")
_KNOWN = frozenset(_REQUIRED + _OPTIONAL)
_COMPLIANCE = {
    "palace": "compliant",
    "toc": "compliant",
    "partial": "partial",
    "independent": "non-compliant",
}


class ConsumersError(Exception):
    def __init__(self, problems: list[str]):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


@dataclass(frozen=True)
class Consumer:
    name: str
    repo: str
    entry: str
    kinds: tuple[str, ...]
    mode: str
    via: str | None = None
    reads: tuple[str, ...] = ()
    kinds_toc: tuple[str, ...] = ()
    other: str | None = None
    note: str | None = None
    issue: str | None = None


def compliance(c: Consumer) -> str:
    """'compliant' (palace/toc), 'partial', or 'non-compliant' (independent)."""
    return _COMPLIANCE[c.mode]


def noncompliant(consumers) -> tuple[Consumer, ...]:
    """The consumers whose compliance is not 'compliant' (partial and non-compliant)."""
    return tuple(c for c in consumers if compliance(c) != "compliant")


def _str_list(v, where: str, problems: list[str], allowed: set[str] | None = None) -> tuple:
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        problems.append(f"{where}: must be a list of strings")
        return ()
    if allowed is not None:
        for x in v:
            if x not in allowed:
                problems.append(f"{where}: unknown kind {x!r} (standard: {sorted(allowed)})")
    return tuple(v)


def _opt_str(e: dict, key: str, where: str, problems: list[str]) -> str | None:
    v = e.get(key)
    if v is not None and not isinstance(v, str):
        problems.append(f"{where}.{key}: must be a string or null")
        return None
    return v


def load(path: Path = DEFAULT) -> tuple[Consumer, ...]:
    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as e:
        raise ConsumersError([f"cannot read {path}: {e}"]) from e
    if not isinstance(raw, dict):
        raise ConsumersError([f"{path.name}: top level must be a mapping"])
    problems: list[str] = []
    if raw.get("schema") != SCHEMA:
        problems.append(f"schema: must be {SCHEMA}, got {raw.get('schema')!r}")
    entries = raw.get("consumers")
    if not isinstance(entries, list):
        problems.append("consumers: must be a list")
        raise ConsumersError(problems)
    kind_names = {k.name for k in _recipe.current().kinds}
    out: list[Consumer] = []
    for i, e in enumerate(entries):
        label = e.get("name") if isinstance(e, dict) and isinstance(e.get("name"), str) else None
        where = f"consumers[{i}]" + (f" ({label})" if label else "")
        if not isinstance(e, dict):
            problems.append(f"{where}: must be a mapping")
            continue
        for f in sorted(set(e) - _KNOWN, key=str):
            problems.append(f"{where}.{f}: unknown field")
        for f in _REQUIRED:
            if f not in e or e[f] in (None, ""):
                problems.append(f"{where}.{f}: required")
        for f in ("name", "repo", "entry"):
            if f in e and e[f] not in (None, "") and not isinstance(e[f], str):
                problems.append(f"{where}.{f}: must be a string")
        mode = e.get("mode")
        if mode not in (None, "") and mode not in MODES:
            problems.append(f"{where}.mode: {mode!r} is not one of {list(MODES)}")
        # `kinds: []` is valid: a consumer may read only non-corpus files (see `other`).
        kinds = (_str_list(e["kinds"], f"{where}.kinds", problems, kind_names)
                 if e.get("kinds") is not None else ())
        reads = _str_list(e["reads"], f"{where}.reads", problems) if "reads" in e else ()
        kinds_toc = (_str_list(e["kinds_toc"], f"{where}.kinds_toc", problems, kind_names)
                     if "kinds_toc" in e else ())
        via = _opt_str(e, "via", where, problems)
        other = _opt_str(e, "other", where, problems)
        note = _opt_str(e, "note", where, problems)
        issue = _opt_str(e, "issue", where, problems)
        out.append(Consumer(
            name=str(e.get("name") or ""), repo=str(e.get("repo") or ""),
            entry=str(e.get("entry") or ""), kinds=kinds, mode=str(mode or ""),
            via=via, reads=reads, kinds_toc=kinds_toc, other=other, note=note, issue=issue,
        ))
    if problems:
        raise ConsumersError(problems)
    return tuple(out)
