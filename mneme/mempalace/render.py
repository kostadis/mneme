"""Render derived mempalace config from the single authority (FR-016, Principle V).

The per-wing `mempalace.yaml` files and the root `.mempalaceignore` are regenerated
from `.mneme/mempalace.yaml` + the recipe, and stamped with a SHA-256 of
`(authority + recipe version)`. `status` recomputes the hash to detect a stale or
hand-edited derived file. Reuses `hypostasis.render.subtree_sha256` for hashing.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path

import yaml

from hypostasis.render import subtree_sha256
from mneme.corpus import config as _cconfig
from mneme.corpus import resolve as _cresolve
from mneme.corpus import toc as _toc

from .models import CampaignMempalaceConfig, Recipe, RenderedArtifact

STAMP_PREFIX = "# mneme-rendered; source-sha256:"
STAMP_SUFFIX = "do-not-edit"
IGNORE_RELPATH = ".mempalaceignore"


def _context(cfg: CampaignMempalaceConfig, recipe: Recipe) -> dict:
    """The exact authority slice a render derives from — hashed for drift detection."""
    return {
        "campaign": cfg.campaign,
        "recipe_version": recipe.version,
        "baseline_exclusions": list(recipe.mechanical.baseline_exclusions),
        "extra_exclusions": list(cfg.extra_exclusions),
        "wings": [
            {
                "name": w.name,
                "source": w.source,
                "trust": w.trust,
                "rooms": [asdict(r) for r in w.rooms],
            }
            for w in cfg.wings
        ],
    }


def source_hash(cfg: CampaignMempalaceConfig, recipe: Recipe) -> str:
    return subtree_sha256(_context(cfg, recipe))


def _stamp(digest: str, body: str) -> str:
    return f"{STAMP_PREFIX} {digest}; {STAMP_SUFFIX}\n{body}"


def read_stamp(path: Path) -> str | None:
    """Return the stamped source-sha256 from a derived file's header, or None."""
    try:
        first = path.read_text().splitlines()[0]
    except (OSError, IndexError):
        return None
    if STAMP_PREFIX not in first:
        return None
    try:
        return first.split("source-sha256:")[1].split(";")[0].strip()
    except IndexError:
        return None


def _wing_yaml(cfg_wing, store_alias: str | None = None) -> str:
    doc: dict = {}
    # The ROOT wing's mempalace.yaml carries the `palace:` key, so a CLI run from inside
    # the campaign dir walks up to it and resolves to this campaign's store (FR-016).
    if store_alias and cfg_wing.source in (".", ""):
        doc["palace"] = store_alias
    doc["wing"] = cfg_wing.name
    doc["rooms"] = [
        {"name": r.name, "description": r.description, "keywords": list(r.keywords)}
        for r in cfg_wing.rooms
    ]
    return yaml.safe_dump(doc, sort_keys=False, default_flow_style=False)


def _ignore_body(cfg: CampaignMempalaceConfig, recipe: Recipe) -> str:
    lines: list[str] = list(recipe.mechanical.baseline_exclusions)
    lines += list(cfg.extra_exclusions)
    # Double-mine guard (FR-004): exclude every non-root wing source from the root.
    for w in cfg.wings:
        if w.source not in (".", ""):
            lines.append(w.source.rstrip("/") + "/")
    # de-dupe, preserve order
    seen: set[str] = set()
    out = [x for x in lines if not (x in seen or seen.add(x))]
    return "\n".join(out) + "\n"


def render(cfg: CampaignMempalaceConfig, recipe: Recipe) -> list[RenderedArtifact]:
    """Every derived artifact for a campaign (targets RELATIVE to the campaign root)."""
    digest = source_hash(cfg, recipe)
    store_alias = cfg.store.alias if cfg.store is not None else None
    out: list[RenderedArtifact] = []
    for w in cfg.wings:
        target = Path(w.source) / "mempalace.yaml"
        out.append(
            RenderedArtifact(
                target=target, source_sha256=digest, content=_wing_yaml(w, store_alias)
            )
        )
    out.append(
        RenderedArtifact(
            target=Path(IGNORE_RELPATH), source_sha256=digest, content=_ignore_body(cfg, recipe)
        )
    )
    return out


def stamped_text(artifact: RenderedArtifact) -> str:
    return _stamp(artifact.source_sha256, artifact.content)


# ---------------------------------------------------------------------------
# 007 — corpus campaigns (`.mneme/corpus.yaml` present). Wings are derived from the declared
# kinds: one root `mempalace.yaml` (palace pointer + rooms), the TOC snapshot, and no per-wing
# renders. The wing-model path above is unchanged.
# ---------------------------------------------------------------------------

ROOT_YAML = "mempalace.yaml"


def corpus_rooms(recipe: Recipe) -> list[dict]:
    """The union of the recipe kinds' room hints, in recipe order."""
    seen: set[str] = set()
    rooms: list[dict] = []
    for k in recipe.kinds:
        for name in k.rooms_hint:
            if name not in seen:
                seen.add(name)
                rooms.append({"name": name, "description": f"{name} content", "keywords": []})
    return rooms


def corpus_kind_order(ccfg: _cconfig.CorpusConfig, recipe: Recipe) -> list[str]:
    """Declared kinds: standard ones in recipe order, then campaign kinds as declared."""
    std = [k.name for k in recipe.kinds if k.name in ccfg.kinds]
    return std + [n for n in ccfg.kinds if n not in std]


def corpus_wing_split(ccfg: _cconfig.CorpusConfig, recipe: Recipe) -> tuple[list[str], list[str]]:
    """``(canon_wings, index_wings)``: kinds with effective trust `authoritative`, the rest."""
    order = corpus_kind_order(ccfg, recipe)
    canon = [n for n in order if ccfg.kinds[n].trust == "authoritative"]
    return canon, [n for n in order if n not in canon]


def _corpus_digest(cfg: CampaignMempalaceConfig, recipe: Recipe, ccfg) -> str:
    return subtree_sha256({
        "campaign": cfg.campaign,
        "recipe_version": recipe.version,
        "alias": cfg.store.alias if cfg.store is not None else None,
        "corpus_sha256": ccfg.corpus_sha256,
        "rooms": corpus_rooms(recipe),
    })


def _corpus_root_yaml(cfg: CampaignMempalaceConfig, recipe: Recipe) -> str:
    doc: dict = {}
    if cfg.store is not None:
        doc["palace"] = cfg.store.alias  # the CLI walk-up pointer (FR-016)
    doc["rooms"] = corpus_rooms(recipe)
    return yaml.safe_dump(doc, sort_keys=False, default_flow_style=False)


def _load_corpus(recipe: Recipe, campaign_dir: Path) -> _cconfig.CorpusConfig:
    return _cconfig.load(campaign_dir, recipe)


def leftover_wing_renders(campaign_dir: Path) -> list[Path]:
    """Per-wing `mempalace.yaml` / `.mempalaceignore` files mneme's wing model stamped, under
    ``campaign_dir`` (relative paths). The root `mempalace.yaml` is the corpus render, not a
    leftover. Unstamped files are the campaign's own and are never listed."""
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(campaign_dir):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for name in filenames:
            rel = (Path(dirpath) / name).relative_to(campaign_dir)
            if name == IGNORE_RELPATH or (name == ROOT_YAML and rel != Path(ROOT_YAML)):
                if read_stamp(campaign_dir / rel) is not None:
                    found.append(rel)
    return sorted(found)


def write_corpus(
    cfg: CampaignMempalaceConfig, recipe: Recipe, dest_root: Path, resolved=None,
) -> list[Path]:
    """Corpus render: stamped root `mempalace.yaml`, the TOC snapshot (+ `.gitignore` line),
    and removal of leftover stamped wing-model renders. Raises CorpusConfigError. ``resolved``
    is a ResolvedCorpus the caller already built for this recipe (else resolved here)."""
    ccfg = _load_corpus(recipe, dest_root)
    art = RenderedArtifact(
        target=Path(ROOT_YAML), source_sha256=_corpus_digest(cfg, recipe, ccfg),
        content=_corpus_root_yaml(cfg, recipe),
    )
    written: list[Path] = []
    root = dest_root / art.target
    root.write_text(stamped_text(art))
    written.append(root)
    for rel in leftover_wing_renders(dest_root):
        (dest_root / rel).unlink()
    if resolved is None:
        resolved = _cresolve.resolve(ccfg, dest_root, recipe)
    written.append(_toc.write(dest_root, _toc.build(resolved, ccfg, recipe)))
    return written


def coherent_corpus(cfg: CampaignMempalaceConfig, recipe: Recipe, campaign_dir: Path) -> list[Path]:
    """Stale/missing/leftover corpus artifacts (relative paths); empty means coherent. The TOC
    snapshot is NOT judged here: it goes stale with every content edit, and the `corpus` row
    reports that once (toc-stale)."""
    try:
        ccfg = _load_corpus(recipe, campaign_dir)
    except _cconfig.CorpusConfigError:
        return [Path(ROOT_YAML)]  # cannot be judged: never reported coherent
    drifted: list[Path] = []
    if read_stamp(campaign_dir / ROOT_YAML) != _corpus_digest(cfg, recipe, ccfg):
        drifted.append(Path(ROOT_YAML))
    return drifted + leftover_wing_renders(campaign_dir)


def write_all(
    cfg: CampaignMempalaceConfig, recipe: Recipe, dest_root: Path, resolved=None,
) -> list[Path]:
    """Write every derived artifact under ``dest_root`` (a working copy, never the
    active checkout for an upgrade). Returns the written paths."""
    if _cconfig.has_corpus(dest_root):
        return write_corpus(cfg, recipe, dest_root, resolved)
    written: list[Path] = []
    for art in render(cfg, recipe):
        target = dest_root / art.target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(stamped_text(art))
        written.append(target)
    return written


def coherent(cfg: CampaignMempalaceConfig, recipe: Recipe, campaign_dir: Path) -> list[Path]:
    """Return the list of derived targets whose on-disk stamp is stale/missing.

    Empty ⇒ all derived files are coherent with the authority (Principle V).
    """
    if _cconfig.has_corpus(campaign_dir):
        return coherent_corpus(cfg, recipe, campaign_dir)
    digest = source_hash(cfg, recipe)
    drifted: list[Path] = []
    for art in render(cfg, recipe):
        target = campaign_dir / art.target
        if read_stamp(target) != digest:
            drifted.append(art.target)
    return drifted


# ---------------------------------------------------------------------------
# 003 — the store-naming faces rendered from the authority's store pointer.
# These three are MERGE-into-existing-file (config/config.yaml / config.json / .mcp.json),
# so they are value-coherence-checked, not stamped (they share files with other data).
# ---------------------------------------------------------------------------

CONFIG_YAML = "config/config.yaml"  # CampaignGenerator reads ONLY this path (#67)
MCP_JSON = ".mcp.json"


def _canon_and_index_wings(cfg: CampaignMempalaceConfig) -> tuple[str, list[str]]:
    canon = next((w.name for w in cfg.wings if w.trust == "authoritative"), None)
    canon = canon or (cfg.wings[0].name if cfg.wings else cfg.campaign)
    index = [w.name for w in cfg.wings if w.name != canon]
    return canon, index


def render_config_yaml(
    cfg: CampaignMempalaceConfig, campaign_dir: Path, recipe: Recipe | None = None
) -> Path:
    """Merge the `mempalace:` section into the campaign's config/config.yaml (CG search face).
    A corpus campaign gets `canon_wings` + `index_wings` and NO `canon_wing` (007 R8)."""
    path = campaign_dir / CONFIG_YAML
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {}
    if path.is_file():
        doc = yaml.safe_load(path.read_text()) or {}
    if _cconfig.has_corpus(campaign_dir):
        from . import recipe as _recipe

        rec = recipe or _recipe.load(cfg.recipe_version)
        canon_wings, index_wings = corpus_wing_split(_load_corpus(rec, campaign_dir), rec)
        doc["mempalace"] = {"canon_wings": canon_wings, "index_wings": index_wings}
        path.write_text(yaml.safe_dump(doc, sort_keys=False))
        return path
    canon, index = _canon_and_index_wings(cfg)
    doc["mempalace"] = {"canon_wing": canon, "index_wings": index}
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    return path


def render_global_alias(cfg: CampaignMempalaceConfig, config_json: Path) -> Path:
    """Merge this campaign's alias→path into the shared global config.json `palaces` map.

    Read-modify-merge-write — NEVER clobber other campaigns' entries (Principle VI)."""
    import json

    if cfg.store is None:
        raise ValueError("render_global_alias requires a store pointer")
    data: dict = {}
    if config_json.is_file():
        data = json.loads(config_json.read_text() or "{}")
    palaces = dict(data.get("palaces") or {})
    palaces[cfg.store.alias] = str(cfg.store.path)
    data["palaces"] = palaces
    config_json.parent.mkdir(parents=True, exist_ok=True)
    config_json.write_text(json.dumps(data, indent=2) + "\n")
    return config_json


# The ONLY hypostasis-declared env keys that may reach the MCP server entry (GH #26): backend +
# embedder selection. An allow-list, never a pass-through — no *_API_KEY / secret may ever be
# written into .mcp.json. (.mcp.json is a host-local untracked face, so endpoints are fine.)
MCP_ENV_ALLOW = (
    "MEMPALACE_BACKEND",
    "MEMPALACE_EMBEDDING_PROVIDER",
    "MEMPALACE_EMBEDDING_MODEL",
    "MEMPALACE_EMBEDDING_ENDPOINT",
    "MEMPALACE_EMBEDDING_DEVICE",
)


def declared_mcp_env(env: Mapping[str, str] | None) -> dict[str, str]:
    """The allow-listed, non-empty subset of the declared env for the MCP server entry."""
    return {
        k: str(env[k]).strip() for k in MCP_ENV_ALLOW if env and str(env.get(k, "")).strip()
    }


def render_mcp(
    cfg: CampaignMempalaceConfig, campaign_dir: Path, env: Mapping[str, str] | None = None
) -> Path:
    """Merge a `mempalace` stdio server (palace injected) into the campaign's .mcp.json.

    Never hardcodes a path — the palace comes from the authority's store pointer (FR-017).
    `env` is the hypostasis-declared env (`entity.env`); only `MCP_ENV_ALLOW` keys are copied
    so the MCP server runs the same backend/embedder as the CLI (GH #26)."""
    import json

    if cfg.store is None:
        raise ValueError("render_mcp requires a store pointer")
    path = campaign_dir / MCP_JSON
    data: dict = {}
    if path.is_file():
        data = json.loads(path.read_text() or "{}")
    servers = dict(data.get("mcpServers") or {})
    servers["mempalace"] = {
        "type": "stdio",
        "command": "mempalace-mcp",
        "env": {"MEMPALACE_PALACE_PATH": str(cfg.store.path), **declared_mcp_env(env)},
    }
    data["mcpServers"] = servers
    path.write_text(json.dumps(data, indent=2) + "\n")
    return path


def render_faces(
    cfg: CampaignMempalaceConfig, recipe: Recipe, campaign_dir: Path, config_json: Path,
    env: Mapping[str, str] | None = None, resolved=None,
) -> list[Path]:
    """Render ALL faces from the one authority (FR-002a): the stamped wing yamls +
    .mempalaceignore (incl. the root `palace:` pointer), plus the three merge faces."""
    written = write_all(cfg, recipe, campaign_dir, resolved)
    written.append(render_config_yaml(cfg, campaign_dir, recipe))
    if cfg.store is not None:
        written.append(render_global_alias(cfg, config_json))
        written.append(render_mcp(cfg, campaign_dir, env))
    return written


def faces_coherent(
    cfg: CampaignMempalaceConfig, campaign_dir: Path, config_json: Path,
    env: Mapping[str, str] | None = None,
) -> list[str]:
    """Value-coherence of the merge faces vs the authority's store pointer (FR-015/SC-008).

    Returns a list of mismatches; empty ⇒ every store-naming face agrees with the authority."""
    import json

    bad: list[str] = []
    if cfg.store is None:
        return bad
    want = str(cfg.store.path)
    # cli_pointer: the root wing's mempalace.yaml carries palace: alias
    root = next((w.source for w in cfg.wings if w.source in (".", "")), None)
    if _cconfig.has_corpus(campaign_dir):  # the corpus render's root yaml carries the pointer
        try:
            doc = yaml.safe_load((campaign_dir / ROOT_YAML).read_text().split("\n", 1)[-1]) or {}
            if doc.get("palace") != cfg.store.alias:
                bad.append("cli_pointer: root mempalace.yaml palace: != authority alias")
        except OSError:
            bad.append("cli_pointer: root mempalace.yaml missing")
    elif root is not None:
        rp = campaign_dir / (root if root not in (".", "") else "") / "mempalace.yaml"
        try:
            doc = yaml.safe_load(rp.read_text().split("\n", 1)[-1]) or {}
            if doc.get("palace") != cfg.store.alias:
                bad.append("cli_pointer: root mempalace.yaml palace: != authority alias")
        except OSError:
            bad.append("cli_pointer: root mempalace.yaml missing")
    # global alias
    if config_json.is_file():
        palaces = (json.loads(config_json.read_text() or "{}").get("palaces") or {})
        if palaces.get(cfg.store.alias) != want:
            bad.append("global_alias: config.json palaces entry != store path")
    else:
        bad.append("global_alias: config.json missing")
    # mcp face
    mcp = campaign_dir / MCP_JSON
    if mcp.is_file():
        servers = json.loads(mcp.read_text() or "{}").get("mcpServers") or {}
        mcp_env = (servers.get("mempalace") or {}).get("env") or {}
        if mcp_env.get("MEMPALACE_PALACE_PATH") != want:
            bad.append("mcp: .mcp.json mempalace palace != store path")
        if env is not None:
            # declared backend/embedder must be exactly what the file carries (a missing or
            # no-longer-declared key means the MCP server runs a different embedder: stale)
            want_env = declared_mcp_env(env)
            have_env = {k: str(mcp_env[k]) for k in MCP_ENV_ALLOW if mcp_env.get(k)}
            if have_env != want_env:
                keys = sorted(k for k in MCP_ENV_ALLOW if want_env.get(k) != have_env.get(k))
                bad.append(f"mcp: .mcp.json embedder/backend env out of date ({', '.join(keys)})")
    else:
        bad.append("mcp: .mcp.json missing")
    return bad
