"""The corpus TOC: a derived, host-local SNAPSHOT (feature 007, R5, `contracts/toc-json.md`).

`<campaign>/.mneme/corpus.toc.json` records what the declaration resolved to the last time it
was rendered. It is for inspection and for status's `toc-stale` check. **Consumers never read
it** (GM decision 2026-10-23, FR-012/021): they re-resolve through mneme on every call, so a
file added to a declared folder or a hand edit to this snapshot cannot mislead them.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from mneme import __version__
from mneme.mempalace.models import Recipe

from .config import CorpusConfig
from .resolve import ResolvedCorpus

SCHEMA = 1
TOC_RELPATH = Path(".mneme") / "corpus.toc.json"
GITIGNORE_LINE = ".mneme/corpus.toc.json"

MISSING = "missing"
STALE = "stale"
OK = "ok"


class TocError(Exception):
    """The snapshot exists but cannot be read as a TOC."""


@dataclass(frozen=True)
class TocCheck:
    state: str  # MISSING | STALE | OK
    reasons: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.state == OK


def toc_path(campaign_dir: Path) -> Path:
    return Path(campaign_dir) / TOC_RELPATH


def build(resolved: ResolvedCorpus, cfg: CorpusConfig, recipe: Recipe) -> dict:
    """The TOC document for a resolution (schema 1). Pure: touches nothing on disk."""
    kinds: dict[str, dict] = {}
    for name, k in resolved.kinds.items():
        files = []
        for f in k.files:  # already sorted by declared path
            entry: dict = {"path": f.path}
            if f.target:
                entry["target"] = f.target
            entry.update({"sha256": f.sha256, "minable": f.minable, "mined_as": f.mined_as})
            files.append(entry)
        kinds[name] = {
            "standard": k.standard,
            "trust": k.trust,
            "files": files,
            "not_materialized": list(k.not_materialized),
            "missing": list(k.missing),
        }
    return {
        "schema": SCHEMA,
        "generated_by": f"mneme {__version__}",
        "campaign": cfg.campaign,
        "corpus_sha256": cfg.corpus_sha256,
        "recipe_version": recipe.version,
        "valid": resolved.valid,
        "findings": [f.as_dict() for f in resolved.findings],
        "kinds": kinds,
    }


def _ensure_gitignored(campaign_dir: Path) -> None:
    gi = Path(campaign_dir) / ".gitignore"
    text = gi.read_text() if gi.is_file() else ""
    if GITIGNORE_LINE in {ln.strip().lstrip("/") for ln in text.splitlines()}:
        return
    sep = "" if not text or text.endswith("\n") else "\n"
    gi.write_text(text + sep + GITIGNORE_LINE + "\n")


def write(campaign_dir: Path, toc: dict) -> Path:
    """Write the snapshot atomically, then make sure the campaign's `.gitignore` lists it
    (it is host-local and must never be tracked, R5). Returns the TOC path."""
    path = toc_path(campaign_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".corpus.toc.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(toc, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    _ensure_gitignored(campaign_dir)
    return path


def read(campaign_dir: Path) -> dict | None:
    """The snapshot, or None when there is none. Raises TocError if it exists but is not a
    TOC (unknown is never ok). For status and inspection only; consumers do not call this."""
    path = toc_path(campaign_dir)
    try:
        text = path.read_text()
    except FileNotFoundError:
        return None
    except OSError as e:
        raise TocError(f"cannot read {path}: {e}") from e
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as e:
        raise TocError(f"{path} is not valid JSON: {e}") from e
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA or not isinstance(
        doc.get("kinds"), dict
    ):
        raise TocError(f"{path} is not a schema-{SCHEMA} corpus TOC")
    return doc


def _paths(kind: dict) -> set[str]:
    return {f.get("path", "") for f in kind.get("files", []) if isinstance(f, dict)}


def _hashes(kind: dict) -> dict[tuple, tuple]:
    return {
        (f.get("path"),): (f.get("sha256"), f.get("target"), f.get("minable"), f.get("mined_as"))
        for f in kind.get("files", []) if isinstance(f, dict)
    }


def verify(campaign_dir: Path, fresh: dict) -> TocCheck:
    """Compare the snapshot with ``fresh`` (a `build` of a fresh resolution): missing, stale or
    ok. Stale covers a changed stamp, a changed file set (a file added to a declared folder, a
    hand-edited list) and changed hashes, plus anything else that differs."""
    try:
        snap = read(campaign_dir)
    except TocError as e:
        return TocCheck(STALE, (f"unreadable snapshot: {e}",))
    if snap is None:
        return TocCheck(MISSING)
    reasons: list[str] = []
    for key in ("corpus_sha256", "recipe_version", "campaign"):
        if snap.get(key) != fresh.get(key):
            reasons.append(f"stamp differs: {key}")
    sk, fk = snap.get("kinds", {}), fresh.get("kinds", {})
    for name in sorted(set(sk) | set(fk)):
        if name not in sk:
            reasons.append(f"kind '{name}' is declared now but not in the snapshot")
            continue
        if name not in fk:
            reasons.append(f"kind '{name}' is in the snapshot but no longer declared")
            continue
        a, b = sk[name], fk[name]
        pa, pb = _paths(a), _paths(b)
        if pa != pb:
            added, gone = sorted(pb - pa), sorted(pa - pb)
            reasons.append(
                f"kind '{name}' file set differs"
                + (f"; new: {', '.join(added)}" if added else "")
                + (f"; gone: {', '.join(gone)}" if gone else "")
            )
        elif _hashes(a) != _hashes(b):
            reasons.append(f"kind '{name}' file hashes/targets differ")
        if {k: v for k, v in a.items() if k != "files"} != {
            k: v for k, v in b.items() if k != "files"
        }:
            reasons.append(f"kind '{name}' trust/not_materialized/missing differ")
    if snap.get("valid") != fresh.get("valid") or snap.get("findings") != fresh.get("findings"):
        reasons.append("validity or findings differ")
    return TocCheck(STALE if reasons else OK, tuple(reasons))


def files_for(toc: dict, kind: str) -> list[dict] | None:
    """The file entries of ``kind``. None means the kind is NOT DECLARED for this campaign;
    an empty list means it is declared and resolves to nothing (FR-013) — never conflate them."""
    k = toc.get("kinds", {}).get(kind)
    if k is None:
        return None
    return list(k.get("files", []))
