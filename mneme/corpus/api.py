"""The one consumer-facing resolution path (feature 007, FR-012/013/021, SC-008).

`mneme corpus toc` and the `corpus_files` MCP tool both answer through `consult`, so the two
readers cannot diverge. It resolves `corpus.yaml` against the disk on every call and never
reads the TOC snapshot (GM decision 2026-10-23).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from mneme.mempalace import recipe as _recipe
from mneme.mempalace.models import Recipe

from . import resolve as _resolve
from . import toc as _toc
from .config import CorpusConfigError, has_corpus, load

INVALID = "invalid"
NOT_DECLARED = "not-declared"


def campaign_recipe(campaign_dir: Path) -> Recipe:
    """The recipe the campaign's authority adopted (what mining, prune, regenerate and status
    resolve with), so every reader validates `corpus.yaml` identically. Read tolerantly: no
    authority, or an unreadable/uninstalled version, falls back to the current recipe."""
    try:
        raw = yaml.safe_load((Path(campaign_dir) / ".mneme" / "mempalace.yaml").read_text())
        return _recipe.load(str(raw["recipe_version"]))
    except (OSError, yaml.YAMLError, TypeError, KeyError, ValueError, _recipe.RecipeError):
        return _recipe.current()


def fresh(campaign_dir: Path, recipe: Recipe) -> dict:
    """The TOC document for the campaign as the disk says it is NOW. Raises
    CorpusConfigError if `corpus.yaml` is unreadable or violates the contract; a resolution
    that finds problems comes back with ``valid: false`` and its findings."""
    cfg = load(campaign_dir, recipe)
    resolved = _resolve.resolve(cfg, campaign_dir, recipe)
    return _toc.build(resolved, cfg, recipe)


def consult(campaign_dir: Path, recipe: Recipe, kind: str | None = None) -> dict:
    """Resolve fresh and answer a consumer. Returns ``{"toc": <doc>}`` (restricted to ``kind``
    when given) or ``{"error": "invalid"|"not-declared", "detail": str, "findings": [...]}``.
    An undeclared kind is an error, never an empty list (FR-013)."""
    if not has_corpus(Path(campaign_dir)):
        return {"error": NOT_DECLARED, "findings": [],
                "detail": "campaign declares no corpus (.mneme/corpus.yaml is absent)"}
    try:
        doc = fresh(campaign_dir, recipe)
    except CorpusConfigError as e:
        return {"error": INVALID, "detail": str(e), "findings": [f.as_dict() for f in e.findings]}
    if not doc["valid"]:
        lines = "; ".join(f"{f['code']}: {f['detail']}" for f in doc["findings"])
        return {"error": INVALID, "detail": f"corpus does not resolve: {lines}",
                "findings": doc["findings"]}
    if kind is not None:
        if _toc.files_for(doc, kind) is None:
            return {"error": NOT_DECLARED, "findings": [],
                    "detail": f"kind '{kind}' is not declared for this campaign"}
        doc = {**doc, "kinds": {kind: doc["kinds"][kind]}}
    return {"toc": doc}


NO_BRIEF = "no-brief"
BRIEF_UNAVAILABLE = "brief-unavailable"


def brief(campaign_dir: Path, recipe: Recipe) -> dict:
    """The briefing answer (mytools#87): the whole TOC as a map, plus the GM's load-now set.

    Returns ``{"brief": <doc>}`` or ``{"error": ..., "detail": ..., "findings": [...]}``.
    Refuses — never guesses — when the corpus is invalid or undeclared (as `consult`), when
    `corpus.yaml` has no `brief:` (``no-brief``), or when a brief file is declared but absent
    on this checkout (``brief-unavailable``: not materialized or missing). Paths and sizes
    only, never contents: the consumer reads the files itself."""
    answer = consult(campaign_dir, recipe)
    if "error" in answer:
        return answer
    doc = answer["toc"]
    cfg = load(campaign_dir, recipe)  # parsed again: consult already proved it loads
    if not cfg.brief:
        return {"error": NO_BRIEF, "findings": [],
                "detail": "corpus.yaml declares no `brief:` (the load-now file list); "
                          "add one before using a briefing consumer"}
    root = Path(campaign_dir)
    toc: dict[str, dict] = {}
    by_path: dict[str, list[tuple[str, str]]] = {}
    for name, k in doc["kinds"].items():
        files = []
        for f in k["files"]:
            files.append({"path": f["path"], "bytes": (root / f["path"]).stat().st_size})
            by_path.setdefault(f["path"], []).append((name, k["trust"]))
        toc[name] = {"trust": k["trust"], "files": files}
    out, absent = [], []
    for p in cfg.brief:
        hits = by_path.get(p)
        if not hits:
            absent.append(p)
            continue
        out.append({"path": p, "kinds": [n for n, _ in hits], "trust": hits[0][1],
                    "bytes": (root / p).stat().st_size})
    if absent:
        return {"error": BRIEF_UNAVAILABLE, "findings": [],
                "detail": "brief files declared but not on this checkout (not materialized "
                          f"or missing): {', '.join(absent)}"}
    return {"brief": {
        "schema": 1,
        "campaign": doc["campaign"],
        "corpus_sha256": doc["corpus_sha256"],
        "valid": True,
        "brief": out,
        "brief_bytes": sum(e["bytes"] for e in out),
        "toc": toc,
    }}
