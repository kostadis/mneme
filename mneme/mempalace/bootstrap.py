"""Bootstrap / consolidate a campaign's authority (US4, FR-012/017).

`starter_config` generates a `.mneme/mempalace.yaml` from the recipe scaffold for a
campaign that has none, choosing the 3-/2-/1-wing pattern that fits what the campaign
has. `consolidate_config` folds an existing campaign's scattered per-wing
`mempalace.yaml` files into the single authority (the one-time migration, FR-017).
Both are written through the working copy by the CLI (never the active checkout).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from hypostasis.models import ConfigEntity

from . import authority as _authority
from . import discover as _discover
from . import recipe as _recipe
from . import render as _render
from .models import CampaignMempalaceConfig, Recipe, Room, Wing


def choose_pattern(campaign_dir: Path, recipe: Recipe):
    """Pick the scaffold pattern that fits the campaign's existing layout."""
    have_chapters = (campaign_dir / "docs" / "chapters").is_dir()
    have_distill = (campaign_dir / "docs" / "distill_extractions").is_dir()
    if have_chapters and have_distill:
        want = "three_wing"
    elif have_chapters:
        want = "two_wing"
    else:
        want = "single_wing"
    for p in recipe.scaffold:
        if p.id == want:
            return p
    return recipe.scaffold[-1] if recipe.scaffold else None


def starter_config(campaign: str, campaign_dir: Path, recipe: Recipe) -> CampaignMempalaceConfig:
    pattern = choose_pattern(campaign_dir, recipe)
    wings: list[Wing] = []
    for t in pattern.wings:
        name = campaign if t.name == "<campaign>" else t.name
        source = t.source_hint or "."
        # only include a wing whose source exists (root "." always does)
        if source != "." and not (campaign_dir / source).is_dir():
            continue
        rooms = tuple(Room(name=r, description=f"{r} content", keywords=(r,)) for r in t.rooms_hint)
        wings.append(Wing(name=name, source=source, trust=t.trust, rooms=rooms))
    if not wings:
        wings = [Wing(name=campaign, source=".", trust="reference", rooms=())]
    return CampaignMempalaceConfig(
        campaign=campaign, recipe_version=recipe.version, wings=tuple(wings)
    )


def consolidate_config(
    campaign: str, campaign_dir: Path, recipe: Recipe
) -> CampaignMempalaceConfig:
    """FR-017: build one authority from existing scattered per-wing mempalace.yaml files."""
    wings: list[Wing] = []
    for wing_dir in _discover._existing_wing_dirs(campaign_dir):  # deepest-first
        try:
            doc = yaml.safe_load((wing_dir / "mempalace.yaml").read_text()) or {}
        except (OSError, yaml.YAMLError):
            continue
        rel = str(wing_dir.relative_to(campaign_dir)) or "."
        rooms = tuple(
            Room(
                name=str(r.get("name", "")),
                description=str(r.get("description", "")),
                keywords=tuple(str(k) for k in (r.get("keywords") or ())),
            )
            for r in (doc.get("rooms") or ())
        )
        wings.append(
            Wing(name=str(doc.get("wing", rel)), source=rel, trust="reference", rooms=rooms)
        )
    if not wings:
        return starter_config(campaign, campaign_dir, recipe)
    return CampaignMempalaceConfig(
        campaign=campaign, recipe_version=recipe.version, wings=tuple(wings)
    )


def write_into(cfg: CampaignMempalaceConfig, recipe: Recipe, campaign_dir: Path) -> list[Path]:
    """Write the authority + render derived files into ``campaign_dir``."""
    written = [_authority.write(cfg, campaign_dir)]
    written += _render.write_all(cfg, recipe, campaign_dir)
    return written


def bootstrap(
    entity: ConfigEntity,
    campaign: str,
    *,
    consolidate: bool = False,
    state_dir: Path | None = None,
    git_runner=None,
) -> str:
    """Write a starter (or consolidated) authority for one campaign into the working
    copy and push a proposal branch. Returns the branch."""
    from .publish import _clone_workcopy

    rec = _recipe.current()
    wc = _clone_workcopy(entity, state_dir, git_runner)
    branch = f"mneme/bootstrap-{campaign}"
    wc.checkout_branch(branch)
    camp_dir = wc.path / campaign
    if consolidate or _authority.has_authority(camp_dir):
        cfg = consolidate_config(campaign, camp_dir, rec)
    else:
        cfg = starter_config(campaign, camp_dir, rec)
    write_into(cfg, rec, camp_dir)
    if wc.commit_all(f"mneme: bootstrap mempalace authority for {campaign}"):
        wc.push(branch)
    return branch
