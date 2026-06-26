"""Honest per-campaign conformance (US2, FR-005/008/027 — Principle I).

Reports observed state from the silicon: render-stamp coherence, the `mempalace`
source-vs-index drift signal, and the authority-vs-recipe comparison paired with the
human's recorded dispositions. A deliberate, recorded divergence is NOT a failure;
an undispositioned one is "needs a decision" and IS (FR-027). mneme never guesses
*why* a campaign diverges — it reads the recorded reason or flags its absence.
"""

from __future__ import annotations

from hypostasis.models import ConfigEntity

from . import authority as _authority
from . import discover as _discover
from . import recipe as _recipe
from . import render as _render
from .authority import AuthorityError
from .discover import CampaignRef
from .models import (
    CampaignMempalaceConfig,
    ConformanceReport,
    ConformanceRow,
    Recipe,
    State,
)
from .recipe import RecipeError
from .runner import MempalaceRunner

# Stable divergence keys (see contracts/recipe.schema.md)
DIV_VERSION_BEHIND = "recipe.version.behind"
DIV_SCAFFOLD_NOMATCH = "scaffold.nomatch"


def _scaffold_matches(cfg: CampaignMempalaceConfig, recipe: Recipe) -> bool:
    """True iff the campaign's wing-name set matches any recommended scaffold pattern
    (with `<campaign>` standing for the campaign's own reference wing). Scaffold is
    advisory/overridable — a non-match is only a problem when undispositioned."""
    have = {w.name for w in cfg.wings}
    for pattern in recipe.scaffold:
        want = {(cfg.campaign if t.name == "<campaign>" else t.name) for t in pattern.wings}
        if have == want:
            return True
    return False


def _recipe_row(cfg: CampaignMempalaceConfig, recipe: Recipe) -> ConformanceRow:
    # 1) version behind current → upgrade available (pending by default; deliberate if recorded)
    if cfg.recipe_version != recipe.version:
        disp = cfg.disposition_for(DIV_VERSION_BEHIND)
        if disp and disp.kind == "deliberate":
            return ConformanceRow(
                cfg.campaign, "recipe", State.DIVERGENT_DELIBERATE,
                observed=cfg.recipe_version, expected=recipe.version, disposition=disp,
                note=f"staying on v{cfg.recipe_version} by choice: {disp.rationale}",
            )
        return ConformanceRow(
            cfg.campaign, "recipe", State.DIVERGENT_PENDING,
            observed=cfg.recipe_version, expected=recipe.version,
            note="upgrade available, not yet adopted",
        )
    # 2) scaffold deviation (advisory) → needs a decision only when undispositioned
    if not _scaffold_matches(cfg, recipe):
        disp = cfg.disposition_for(DIV_SCAFFOLD_NOMATCH)
        if disp and disp.kind == "deliberate":
            return ConformanceRow(
                cfg.campaign, "recipe", State.DIVERGENT_DELIBERATE, disposition=disp,
                note=f"non-standard wings by choice: {disp.rationale}",
            )
        if disp and disp.kind == "pending":
            return ConformanceRow(
                cfg.campaign, "recipe", State.DIVERGENT_PENDING, disposition=disp,
                note="non-standard wings; adoption pending",
            )
        return ConformanceRow(
            cfg.campaign, "recipe", State.DIVERGENT_UNDISPOSITIONED,
            note="wing structure matches no recommended scaffold and no reason is recorded "
            "— needs a decision (adopt a scaffold, or record it as deliberate)",
        )
    return ConformanceRow(
        cfg.campaign, "recipe", State.CONFORMANT,
        observed=cfg.recipe_version, note="on current recipe",
    )


def _campaign_rows(
    ref: CampaignRef, recipe: Recipe, runner: MempalaceRunner
) -> list[ConformanceRow]:
    if not ref.has_authority:
        return [
            ConformanceRow(
                ref.name, "recipe", State.MISSING_CONFIG,
                note="no .mneme/mempalace.yaml — skipped (run `mneme mp bootstrap`)",
            )
        ]
    try:
        cfg = _authority.load(ref.path)
    except AuthorityError as e:
        return [
            ConformanceRow(ref.name, "recipe", State.INVALID_CONFIG, note="; ".join(e.problems))
        ]
    try:
        rec = _recipe.load(cfg.recipe_version)
    except RecipeError:
        rec = recipe  # fall back to current for the comparison

    rows = [_recipe_row(cfg, recipe)]

    drifted = _render.coherent(cfg, rec, ref.path)
    if drifted:
        rows.append(
            ConformanceRow(
                ref.name, "render", State.STALE_RENDER,
                note=f"derived files out of sync: {', '.join(str(d) for d in drifted)}",
            )
        )
    else:
        rows.append(
            ConformanceRow(ref.name, "render", State.CONFORMANT, note="derived files coherent")
        )

    stale = runner.is_stale(ref.path)
    rows.append(
        ConformanceRow(
            ref.name, "index", State.STALE if stale else State.BUILT,
            note="documents changed since last index" if stale else "index up to date",
        )
    )
    return rows


def check_dir(
    campaign_dir, *, runner: MempalaceRunner | None = None
) -> ConformanceReport:
    """Conformance of a campaign at an arbitrary path (e.g. a working copy) — used by
    post-migration verification (FR-026) where the dir is not the active checkout."""
    from pathlib import Path

    from . import authority as _auth
    from .discover import CampaignRef, _existing_wing_dirs

    cdir = Path(campaign_dir)
    ref = CampaignRef(
        name=cdir.name,
        path=cdir,
        has_authority=_auth.has_authority(cdir),
        wing_dirs=_existing_wing_dirs(cdir),
    )
    rec = _recipe.current()
    runner = runner or MempalaceRunner.for_venv(None)
    return ConformanceReport(rows=tuple(_campaign_rows(ref, rec, runner)))


def report(
    entity: ConfigEntity,
    campaign: str | None = None,
    *,
    runner: MempalaceRunner | None = None,
) -> ConformanceReport:
    recipe = _recipe.current()
    runner = runner or MempalaceRunner.for_venv(_venv(entity))
    refs = [_discover.find(entity, campaign)] if campaign else _discover.discover(entity)
    rows: list[ConformanceRow] = []
    for ref in refs:
        rows.extend(_campaign_rows(ref, recipe, runner))
    return ConformanceReport(rows=tuple(rows))


def format_row(row: ConformanceRow) -> str:
    flag = "ok " if row.ok else "FAIL"
    return f"{flag} {row.campaign:20} {row.dimension:7} {row.state.value:26} {row.note}"


def _venv(entity: ConfigEntity):
    return entity.venv if entity.venv and str(entity.venv) != "." else None
