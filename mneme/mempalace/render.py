"""Render derived mempalace config from the single authority (FR-016, Principle V).

The per-wing `mempalace.yaml` files and the root `.mempalaceignore` are regenerated
from `.mneme/mempalace.yaml` + the recipe, and stamped with a SHA-256 of
`(authority + recipe version)`. `status` recomputes the hash to detect a stale or
hand-edited derived file. Reuses `hypostasis.render.subtree_sha256` for hashing.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import yaml

from hypostasis.render import subtree_sha256

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


def write_all(cfg: CampaignMempalaceConfig, recipe: Recipe, dest_root: Path) -> list[Path]:
    """Write every derived artifact under ``dest_root`` (a working copy, never the
    active checkout for an upgrade). Returns the written paths."""
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
    digest = source_hash(cfg, recipe)
    drifted: list[Path] = []
    for art in render(cfg, recipe):
        target = campaign_dir / art.target
        if read_stamp(target) != digest:
            drifted.append(art.target)
    return drifted


# ---------------------------------------------------------------------------
# 003 — the store-naming faces rendered from the authority's store pointer.
# These three are MERGE-into-existing-file (config.yaml / config.json / .mcp.json),
# so they are value-coherence-checked, not stamped (they share files with other data).
# ---------------------------------------------------------------------------

CONFIG_YAML = "config.yaml"
MCP_JSON = ".mcp.json"


def _canon_and_index_wings(cfg: CampaignMempalaceConfig) -> tuple[str, list[str]]:
    canon = next((w.name for w in cfg.wings if w.trust == "authoritative"), None)
    canon = canon or (cfg.wings[0].name if cfg.wings else cfg.campaign)
    index = [w.name for w in cfg.wings if w.name != canon]
    return canon, index


def render_config_yaml(cfg: CampaignMempalaceConfig, campaign_dir: Path) -> Path:
    """Merge the `mempalace:` section into the campaign's config.yaml (CG search face)."""
    path = campaign_dir / CONFIG_YAML
    doc = {}
    if path.is_file():
        doc = yaml.safe_load(path.read_text()) or {}
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


def render_mcp(cfg: CampaignMempalaceConfig, campaign_dir: Path) -> Path:
    """Merge a `mempalace` stdio server (palace injected) into the campaign's .mcp.json.

    Never hardcodes a path — the palace comes from the authority's store pointer (FR-017)."""
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
        "env": {"MEMPALACE_PALACE_PATH": str(cfg.store.path)},
    }
    data["mcpServers"] = servers
    path.write_text(json.dumps(data, indent=2) + "\n")
    return path


def render_faces(
    cfg: CampaignMempalaceConfig, recipe: Recipe, campaign_dir: Path, config_json: Path
) -> list[Path]:
    """Render ALL faces from the one authority (FR-002a): the stamped wing yamls +
    .mempalaceignore (incl. the root `palace:` pointer), plus the three merge faces."""
    written = write_all(cfg, recipe, campaign_dir)
    written.append(render_config_yaml(cfg, campaign_dir))
    if cfg.store is not None:
        written.append(render_global_alias(cfg, config_json))
        written.append(render_mcp(cfg, campaign_dir))
    return written


def faces_coherent(
    cfg: CampaignMempalaceConfig, campaign_dir: Path, config_json: Path
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
    if root is not None:
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
        env = (servers.get("mempalace") or {}).get("env") or {}
        if env.get("MEMPALACE_PALACE_PATH") != want:
            bad.append("mcp: .mcp.json mempalace palace != store path")
    else:
        bad.append("mcp: .mcp.json missing")
    return bad
