"""Resolve the recipe against a campaign → the recommended target config (FR-022/009).

The recommendation bumps the campaign to the current recipe version while
**preserving its content choices** (wings, rooms, extra exclusions). An upgrade that
would override a deliberate mechanical disposition is surfaced as a *conflict*, not
silently applied (FR-009).
"""

from __future__ import annotations

from dataclasses import replace

from . import recipe as _recipe
from .models import CampaignMempalaceConfig, Recipe, TargetConfig


def _prior_baseline(cfg: CampaignMempalaceConfig) -> tuple[str, ...] | None:
    """Baseline exclusions of the recipe the campaign is on now; None when that recipe is
    not installed (the delta is then unknown, not the whole baseline)."""
    try:
        return _recipe.load(cfg.recipe_version).mechanical.baseline_exclusions
    except (_recipe.RecipeError, ValueError):
        return None


def resolve(cfg: CampaignMempalaceConfig, recipe: Recipe, *, corpus: bool = False) -> TargetConfig:
    # Recommended = same wings/rooms/extras, advanced to the current recipe version.
    recommended = replace(cfg, recipe_version=recipe.version)

    preserved = [w.name for w in cfg.wings]
    if cfg.extra_exclusions:
        preserved.append("extra_exclusions")

    changed = []
    if cfg.recipe_version != recipe.version:
        changed.append(f"recipe_version {cfg.recipe_version} → {recipe.version}")

    # Baseline exclusions the recipe adds over the campaign's current recipe that it did
    # not already carry as an explicit extra, and ones it drops (informational — they
    # take effect on re-render). A corpus campaign mines an allow-list and renders no
    # ignore file, so baseline exclusions never apply to it (#79).
    added: list[str] = []
    if not corpus:
        prior = _prior_baseline(cfg)
        if prior is None:
            changed.append(f"baseline exclusions: recipe {cfg.recipe_version} not installed, "
                           "delta unknown")
        else:
            have = set(prior) | set(cfg.extra_exclusions)
            new = recipe.mechanical.baseline_exclusions
            added = [x for x in new if x not in have]
            dropped = [x for x in prior if x not in new and x not in cfg.extra_exclusions]
            if dropped:
                changed.append(f"baseline exclusions dropped (no longer excluded): {', '.join(dropped)}")

    # A deliberate disposition against a *mechanical* rule would be overridden by an
    # upgrade that re-imposes it — surface rather than clobber (FR-009).
    conflicts = [
        d.divergence
        for d in cfg.dispositions
        if d.kind == "deliberate" and d.divergence.startswith("mechanical.")
    ]

    return TargetConfig(
        campaign=cfg.campaign,
        recipe_version=recipe.version,
        recommended=recommended,
        added=tuple(added),
        changed=tuple(changed),
        preserved=tuple(preserved),
        conflicts=tuple(conflicts),
    )
