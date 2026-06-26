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


def _wing_yaml(cfg_wing, root_wing_name: str) -> str:
    doc = {
        "wing": cfg_wing.name,
        "rooms": [
            {"name": r.name, "description": r.description, "keywords": list(r.keywords)}
            for r in cfg_wing.rooms
        ],
    }
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
    root_wing = next((w.name for w in cfg.wings if w.source in (".", "")), cfg.campaign)
    out: list[RenderedArtifact] = []
    for w in cfg.wings:
        target = Path(w.source) / "mempalace.yaml"
        out.append(
            RenderedArtifact(target=target, source_sha256=digest, content=_wing_yaml(w, root_wing))
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
