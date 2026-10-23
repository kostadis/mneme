"""Load + validate the campaign's declared corpus (`.mneme/corpus.yaml`, feature 007).

The one tracked place a campaign says which files are its curated content, by kind
(FR-001, `contracts/corpus-yaml.md`). Like `mempalace/authority.py`, loading reports ALL
problems at once as findings, raising `CorpusConfigError` before any side effect. mneme
reads this file and never writes it; nothing is auto-corrected.

This module is the structural half of the validation (data-model rules 1-3, 6 and
unknown keys). Everything that needs the disk or git (symlinks, gitignore, empty corpus)
is `resolve.py`.
"""

from __future__ import annotations

import hashlib
import posixpath
from dataclasses import dataclass
from pathlib import Path

import yaml

from mneme.mempalace.models import TRUST_LEVELS, Recipe

CORPUS_RELPATH = Path(".mneme") / "corpus.yaml"

# Stated by every wing-model mining path that meets a corpus campaign (T017, FR-019).
CORPUS_REFUSAL = "corpus campaign — mining is driven by .mneme/corpus.yaml"

_TOP_KEYS = frozenset({"campaign", "kinds", "campaign_kinds"})
_KIND_KEYS = frozenset({"dirs", "files", "trust", "mined_as"})


@dataclass(frozen=True)
class Finding:
    """One violation: a stable ``code``, the offending ``path`` if any, and a ``detail``."""

    code: str
    detail: str
    path: str | None = None

    def as_dict(self) -> dict:
        if self.path is None:
            return {"code": self.code, "detail": self.detail}
        return {"code": self.code, "path": self.path, "detail": self.detail}

    def line(self) -> str:
        where = f" [{self.path}]" if self.path else ""
        return f"{self.code}{where}: {self.detail}"


class CorpusConfigError(Exception):
    """`.mneme/corpus.yaml` is unreadable or violates the contract."""

    def __init__(self, findings: list[Finding]):
        self.findings = tuple(findings)
        super().__init__(
            "invalid .mneme/corpus.yaml:\n  - " + "\n  - ".join(f.line() for f in findings)
        )


@dataclass(frozen=True)
class KindDecl:
    """One declared kind. ``trust`` is the EFFECTIVE trust (explicit, else the standard
    kind's default); ``standard`` is False for a campaign-defined kind (FR-003a)."""

    name: str
    standard: bool
    trust: str
    dirs: tuple[str, ...] = ()
    files: tuple[str, ...] = ()
    mined_as: bool = False


@dataclass(frozen=True)
class CorpusConfig:
    campaign: str
    kinds: dict[str, KindDecl]  # standard + campaign kinds, in declaration order
    corpus_sha256: str  # sha256 of the exact file bytes (the TOC stamp, R5)
    source_path: Path


def corpus_path(campaign_dir: Path) -> Path:
    return Path(campaign_dir) / CORPUS_RELPATH


def has_corpus(campaign_dir: Path) -> bool:
    """True if the campaign declares a corpus. Every wing-model path asks this (T017)."""
    return corpus_path(campaign_dir).is_file()


def _norm(rel: str) -> tuple[str | None, str | None]:
    """(normalized, None) or (None, reason). Rule 3: relative, POSIX, no escape."""
    if not rel.strip():
        return None, "empty path"
    if "\\" in rel:
        return None, "paths use POSIX separators"
    if rel.startswith("/") or posixpath.isabs(rel):
        return None, "absolute path"
    n = posixpath.normpath(rel)
    if n == ".":
        return None, "names the campaign root itself; declare the folders below it"
    if n == ".." or n.startswith("../"):
        return None, "escapes the campaign root"
    return n, None


def _paths(raw, field: str, kind: str, out: list[Finding]) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
        out.append(Finding("malformed", f"kind '{kind}': `{field}` must be a list of paths"))
        return ()
    seen: dict[str, None] = {}
    for item in raw:
        n, why = _norm(item)
        if n is None:
            out.append(Finding("path-escape", f"kind '{kind}': {why}", path=item))
        else:
            seen[n] = None
    return tuple(seen)


def _decl(
    name: str, raw, *, standard: bool, default_trust: str | None, out: list[Finding]
) -> KindDecl | None:
    if not isinstance(raw, dict):
        out.append(Finding("malformed", f"kind '{name}': must be a mapping"))
        return None
    for key in raw:
        if key not in _KIND_KEYS:
            out.append(
                Finding("unknown-key", f"kind '{name}': unknown key '{key}' "
                        f"(allowed: {', '.join(sorted(_KIND_KEYS))})")
            )
    dirs = _paths(raw.get("dirs"), "dirs", name, out)
    files = _paths(raw.get("files"), "files", name, out)
    if not raw.get("dirs") and not raw.get("files"):
        out.append(Finding("empty-declaration", f"kind '{name}' declares no `dirs` or `files`"))
    trust = raw.get("trust")
    if trust is None:
        if default_trust is None:
            out.append(
                Finding("missing-trust", f"campaign kind '{name}' has no default trust: "
                        f"`trust:` is required (FR-004)")
            )
            return None
        trust = default_trust
    elif trust not in TRUST_LEVELS:
        out.append(
            Finding("invalid-trust", f"kind '{name}': trust '{trust}' not in {TRUST_LEVELS}")
        )
        return None
    mined_as = raw.get("mined_as", False)
    if not isinstance(mined_as, bool):
        out.append(Finding("malformed", f"kind '{name}': `mined_as` must be true or false"))
        mined_as = False
    return KindDecl(name, standard, str(trust), dirs, files, mined_as)


def shared_file_findings(path: str, reaching: list[KindDecl]) -> tuple[list[Finding], str | None]:
    """Data-model rule 6 for one file reachable from several kinds (R2).

    Returns (findings, mining_kind). The mining kind is the single kind whose declaration
    sets ``mined_as``; mneme never picks one (precision decision). Used here for files named
    lexically and by `resolve.py` for files found through `dirs`."""
    if len(reaching) < 2:
        return [], reaching[0].name if reaching else None
    out: list[Finding] = []
    names = ", ".join(sorted(k.name for k in reaching))
    marked = [k.name for k in reaching if k.mined_as]
    if len(marked) != 1:
        out.append(
            Finding(
                "ambiguous-mining-kind",
                f"reachable from kinds [{names}] with {len(marked)} `mined_as: true` "
                "marks; exactly one is required (mempalace can mine a file under one wing)",
                path=path,
            )
        )
    if len({k.trust for k in reaching}) > 1:
        trusts = ", ".join(f"{k.name}={k.trust}" for k in sorted(reaching, key=lambda k: k.name))
        out.append(Finding("trust-conflict", f"kinds disagree on trust: {trusts}", path=path))
    return out, marked[0] if len(marked) == 1 else None


def _under(path: str, d: str) -> bool:
    return path == d or path.startswith(d + "/")


def _lexical_overlaps(kinds: dict[str, KindDecl]) -> list[Finding]:
    """Overlaps visible without the disk: the same file named by two kinds, or a named file
    inside another kind's dir. Dir-vs-dir sharing needs real files, so `resolve.py` finds it."""
    reach: dict[str, list[KindDecl]] = {}
    for k in kinds.values():
        for f in k.files:
            reach.setdefault(f, []).append(k)
    for k in kinds.values():
        for f in list(reach):
            if any(_under(f, d) for d in k.dirs) and k not in reach[f]:
                reach[f].append(k)
    out: list[Finding] = []
    for f in sorted(reach):
        out += shared_file_findings(f, reach[f])[0]
    return out


def _authority_campaign(campaign_dir: Path) -> str | None:
    """The mempalace authority's `campaign:`, read tolerantly; None if there is no authority."""
    try:
        raw = yaml.safe_load((Path(campaign_dir) / ".mneme" / "mempalace.yaml").read_text())
    except (OSError, yaml.YAMLError):
        return None
    if isinstance(raw, dict) and raw.get("campaign") is not None:
        return str(raw["campaign"]).strip()
    return None


def load(campaign_dir: Path, recipe: Recipe) -> CorpusConfig:
    """Parse + validate the campaign's corpus declaration against ``recipe``'s standard
    kinds. Raises CorpusConfigError (every finding at once) on any violation."""
    path = corpus_path(campaign_dir)
    try:
        data = path.read_bytes()
    except OSError as e:
        raise CorpusConfigError([Finding("unreadable", f"cannot read {path}: {e}")]) from e
    try:
        raw = yaml.safe_load(data) or {}
    except yaml.YAMLError as e:
        raise CorpusConfigError([Finding("malformed", f"YAML parse error: {e}")]) from e
    if not isinstance(raw, dict):
        raise CorpusConfigError([Finding("malformed", "top level must be a mapping")])

    out: list[Finding] = []
    for key in raw:
        if key not in _TOP_KEYS:
            out.append(
                Finding("unknown-key", f"unknown top-level key '{key}' "
                        f"(allowed: {', '.join(sorted(_TOP_KEYS))})")
            )

    campaign = str(raw.get("campaign") or "").strip()
    if not campaign:
        out.append(Finding("malformed", "missing required field: campaign"))
    else:  # rule 1
        auth = _authority_campaign(campaign_dir)
        if auth is not None and auth != campaign:
            out.append(
                Finding("campaign-mismatch", f".mneme/corpus.yaml says campaign '{campaign}' "
                        f"but .mneme/mempalace.yaml says '{auth}'")
            )

    standard = {k.name: k for k in recipe.kinds}
    kinds: dict[str, KindDecl] = {}

    std_raw = raw.get("kinds") or {}
    if not isinstance(std_raw, dict):
        out.append(Finding("malformed", "`kinds:` must be a mapping"))
        std_raw = {}
    for name, body in std_raw.items():  # rule 2
        name = str(name)
        if name not in standard:
            hint = " (a campaign-defined kind goes under `campaign_kinds:`)"
            out.append(
                Finding("unknown-kind", f"'{name}' is not a standard kind "
                        f"({', '.join(sorted(standard)) or 'none in this recipe'}){hint}")
            )
            continue
        d = _decl(name, body, standard=True, default_trust=standard[name].default_trust, out=out)
        if d:
            kinds[name] = d

    camp_raw = raw.get("campaign_kinds") or {}
    if not isinstance(camp_raw, dict):
        out.append(Finding("malformed", "`campaign_kinds:` must be a mapping"))
        camp_raw = {}
    for name, body in camp_raw.items():
        name = str(name)
        if name in standard:
            out.append(
                Finding("shadowed-kind", f"campaign kind '{name}' shadows the standard kind of "
                        "the same name; declare it under `kinds:` instead")
            )
            continue
        if name in kinds:
            out.append(Finding("malformed", f"kind '{name}' is declared twice"))
            continue
        d = _decl(name, body, standard=False, default_trust=None, out=out)
        if d:
            kinds[name] = d

    out += _lexical_overlaps(kinds)  # rule 6, the part visible without the disk
    if out:
        raise CorpusConfigError(out)
    return CorpusConfig(campaign, kinds, hashlib.sha256(data).hexdigest(), path)
