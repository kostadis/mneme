"""The one consumer-facing resolution path (feature 007, FR-012/013/021, SC-008).

`mneme corpus toc` and the `corpus_files` MCP tool both answer through `consult`, so the two
readers cannot diverge. It resolves `corpus.yaml` against the disk on every call and never
reads the TOC snapshot (GM decision 2026-10-23).
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from mneme.mempalace import recipe as _recipe
from mneme.mempalace.models import Recipe

from . import resolve as _resolve
from . import toc as _toc
from .config import CorpusConfig, CorpusConfigError, has_corpus, load
from .resolve import ResolvedCorpus

INVALID = "invalid"
NOT_DECLARED = "not-declared"
NO_BRIEF = "no-brief"
BRIEF_UNAVAILABLE = "brief-unavailable"


def campaign_recipe(campaign_dir: Path) -> Recipe:
    """The recipe the campaign's authority adopted (what mining, prune, regenerate and status
    resolve with), so every reader validates `corpus.yaml` identically. Read tolerantly: no
    authority, or an unreadable/uninstalled version, falls back to the current recipe."""
    try:
        raw = yaml.safe_load((Path(campaign_dir) / ".mneme" / "mempalace.yaml").read_text())
        return _recipe.load(str(raw["recipe_version"]))
    except (OSError, yaml.YAMLError, TypeError, KeyError, ValueError, _recipe.RecipeError):
        return _recipe.current()


def _resolve_now(campaign_dir: Path, recipe: Recipe) -> tuple[CorpusConfig, ResolvedCorpus, dict]:
    """Read + validate `corpus.yaml` ONCE and resolve it against the disk (research R3):
    every reader of one answer shares this single load -> resolve -> toc.build."""
    cfg = load(campaign_dir, recipe)
    resolved = _resolve.resolve(cfg, campaign_dir, recipe)
    return cfg, resolved, _toc.build(resolved, cfg, recipe)


def fresh(campaign_dir: Path, recipe: Recipe) -> dict:
    """The TOC document for the campaign as the disk says it is NOW. Raises
    CorpusConfigError if `corpus.yaml` is unreadable or violates the contract; a resolution
    that finds problems comes back with ``valid: false`` and its findings."""
    return _resolve_now(campaign_dir, recipe)[2]


def _consult(campaign_dir: Path, recipe: Recipe, kind: str | None = None):
    """`consult` plus the single resolution it used: ``(answer, cfg, resolved)`` (cfg and
    resolved are None when the corpus is not declared or does not load)."""
    if not has_corpus(Path(campaign_dir)):
        return ({"error": NOT_DECLARED, "findings": [],
                 "detail": "campaign declares no corpus (.mneme/corpus.yaml is absent)"},
                None, None)
    try:
        cfg, resolved, doc = _resolve_now(campaign_dir, recipe)
    except CorpusConfigError as e:
        return ({"error": INVALID, "detail": str(e),
                 "findings": [f.as_dict() for f in e.findings]}, None, None)
    if not doc["valid"]:
        lines = "; ".join(f"{f['code']}: {f['detail']}" for f in doc["findings"])
        return ({"error": INVALID, "detail": f"corpus does not resolve: {lines}",
                 "findings": doc["findings"]}, cfg, resolved)
    if kind is not None:
        if _toc.files_for(doc, kind) is None:
            return ({"error": NOT_DECLARED, "findings": [],
                     "detail": f"kind '{kind}' is not declared for this campaign"}, cfg, resolved)
        doc = {**doc, "kinds": {kind: doc["kinds"][kind]}}
    return {"toc": doc}, cfg, resolved


def consult(campaign_dir: Path, recipe: Recipe, kind: str | None = None) -> dict:
    """Resolve fresh and answer a consumer. Returns ``{"toc": <doc>}`` (restricted to ``kind``
    when given) or ``{"error": "invalid"|"not-declared", "detail": str, "findings": [...]}``.
    An undeclared kind is an error, never an empty list (FR-013)."""
    return _consult(campaign_dir, recipe, kind)[0]


def brief_summary(
    cfg: CorpusConfig, resolved: ResolvedCorpus, campaign_dir: Path
) -> tuple[int, int, int]:
    """(declared count, total bytes of the brief files present on disk, number not present)."""
    here = [p for p in cfg.brief
            if _resolve.brief_standing(cfg, resolved, campaign_dir, p)[0] == "present"]
    return (len(cfg.brief), sum(_size(Path(campaign_dir), p) for p in here),
            len(cfg.brief) - len(here))


def brief(campaign_dir: Path, recipe: Recipe) -> dict:
    """The brief answer (feature 009, `contracts/brief-json.md`): the GM's load-now files plus
    the corpus as a per-kind map, from ONE fresh resolution (R3). Returns ``{"brief": <doc>}``
    or ``{"error": "not-declared"|"invalid"|"no-brief"|"brief-unavailable", "detail",
    "findings"}``. Never queries the palace and never carries file contents (FR-007/007a)."""
    campaign_dir = Path(campaign_dir)
    answer, cfg, resolved = _consult(campaign_dir, recipe)
    if "error" in answer:
        return answer
    if not cfg.brief:
        return {"error": NO_BRIEF, "findings": [],
                "detail": "corpus.yaml declares no `brief:`; add one with "
                          "`mneme corpus migrate-brief CAMPAIGN`"}
    standing = {p: _resolve.brief_standing(cfg, resolved, campaign_dir, p) for p in cfg.brief}
    absent = [p for p, (st, _) in standing.items() if st != "present"]
    if absent:
        return {"error": BRIEF_UNAVAILABLE, "findings": [],
                "detail": "brief file(s) not available on this checkout: " + ", ".join(absent)}
    entries = []
    for path in cfg.brief:
        names = standing[path][1]
        entries.append({"path": path, "kinds": list(names),
                        "trust": resolved.kinds[names[0]].trust, "bytes": _size(campaign_dir, path)})
    kinds = {}
    for name, k in resolved.kinds.items():
        searchable = sum(1 for f in k.files if f.minable and f.mined_as is not None)
        kinds[name] = {"standard": k.standard, "trust": k.trust, "files": len(k.files),
                       "bytes": sum(_size(campaign_dir, f.path) for f in k.files),
                       "searchable": searchable > 0, "searchable_files": searchable}
    return {"brief": {"schema": 1, "campaign": cfg.campaign, "corpus_sha256": cfg.corpus_sha256,
                      "brief": entries, "brief_bytes": sum(e["bytes"] for e in entries),
                      "kinds": kinds}}


def _size(campaign_dir: Path, rel: str) -> int:
    """Bytes of the declared path as it is now (a symlink reports its target's size, R6)."""
    return os.stat(campaign_dir / rel).st_size
