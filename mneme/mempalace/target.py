"""Resolve the recipe against a campaign → the recommended target config (FR-022/009).

The recommendation bumps the campaign to the current recipe version while
**preserving its content choices** (wings, rooms, extra exclusions). An upgrade that
would override a deliberate mechanical disposition is surfaced as a *conflict*, not
silently applied (FR-009).
"""

from __future__ import annotations

from dataclasses import replace

from .models import CampaignMempalaceConfig, Recipe, TargetConfig


def resolve(cfg: CampaignMempalaceConfig, recipe: Recipe) -> TargetConfig:
    # Recommended = same wings/rooms/extras, advanced to the current recipe version.
    recommended = replace(cfg, recipe_version=recipe.version)

    preserved = [w.name for w in cfg.wings]
    if cfg.extra_exclusions:
        preserved.append("extra_exclusions")

    # Baseline exclusions the recipe adds that the campaign did not already carry as
    # an explicit extra (informational — they take effect on re-render).
    added = [x for x in recipe.mechanical.baseline_exclusions if x not in cfg.extra_exclusions]

    changed = []
    if cfg.recipe_version != recipe.version:
        changed.append(f"recipe_version {cfg.recipe_version} → {recipe.version}")

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
