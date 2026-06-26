"""Publish a recipe upgrade (US3, FR-009/010/018) and per-campaign adopt (FR-021).

`preview` computes, per campaign, exactly what an upgrade would change (writes
nothing). `publish` writes the upgrade for every campaign into the private working
copy and pushes a proposal branch — never the active checkout. `adopt` is the
manual per-campaign gate: it stages the upgrade for one campaign on its own branch.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from hypostasis.models import ConfigEntity

from . import authority as _authority
from . import discover as _discover
from . import recipe as _recipe
from . import render as _render
from . import target as _target
from . import workcopy as _workcopy
from .discover import campaigns_root
from .models import TargetConfig


@dataclass
class CampaignPlan:
    campaign: str
    target: TargetConfig

    def line(self) -> str:
        t = self.target
        bits = []
        if t.changed:
            bits.append("; ".join(t.changed))
        if t.added:
            bits.append(f"+{len(t.added)} baseline exclusions")
        if t.conflicts:
            bits.append(f"CONFLICTS: {', '.join(t.conflicts)}")
        preserved = f"preserves {', '.join(t.preserved)}" if t.preserved else "no choices"
        return f"{self.campaign:24} {'; '.join(bits) or 'no change'}  [{preserved}]"


def preview(entity: ConfigEntity) -> list[CampaignPlan]:
    """Per-campaign upgrade plan against the current recipe. Writes nothing."""
    rec = _recipe.current()
    plans: list[CampaignPlan] = []
    for ref in _discover.discover(entity):
        if not ref.has_authority:
            continue
        try:
            cfg = _authority.load(ref.path)
        except _authority.AuthorityError:
            continue
        plans.append(CampaignPlan(ref.name, _target.resolve(cfg, rec)))
    return plans


def _apply_to_workcopy(wc: _workcopy.WorkingCopy, campaign: str, rec) -> None:
    """Write the upgraded authority + re-rendered derived files for one campaign."""
    camp_dir = wc.path / campaign
    cfg = _authority.load(camp_dir)
    upgraded = replace(cfg, recipe_version=rec.version)
    _authority.write(upgraded, camp_dir)
    _render.write_all(upgraded, rec, camp_dir)


def _clone_workcopy(entity: ConfigEntity, state_dir: Path | None, runner) -> _workcopy.WorkingCopy:
    git_runner = runner or _workcopy._run_git
    root = campaigns_root(entity)
    remote = _workcopy.origin_url(root, runner=git_runner)
    if not remote:
        raise _workcopy.WorkingCopyError(
            f"campaigns root {root} has no git origin — cannot publish through version control"
        )
    dest = state_dir or _workcopy.default_state_dir()
    return _workcopy.WorkingCopy.clone(remote, dest, runner=git_runner)


def publish(
    entity: ConfigEntity,
    *,
    recipe_version: str | None = None,
    state_dir: Path | None = None,
    git_runner=None,
) -> tuple[str, list[CampaignPlan]]:
    """Stage the upgrade for all campaigns on a proposal branch; push it. Returns
    (branch, plans). Never touches the active checkout (FR-018)."""
    rec = _recipe.load(recipe_version) if recipe_version else _recipe.current()
    plans = preview(entity)
    wc = _clone_workcopy(entity, state_dir, git_runner)
    branch = f"mneme/recipe-{rec.version}"
    wc.checkout_branch(branch)
    for plan in plans:
        _apply_to_workcopy(wc, plan.campaign, rec)
    if wc.commit_all(f"mneme: propose recipe {rec.version} for all campaigns"):
        wc.push(branch)
    return branch, plans


def adopt(
    entity: ConfigEntity,
    campaign: str,
    *,
    state_dir: Path | None = None,
    git_runner=None,
) -> str:
    """Manual per-campaign gate: stage the upgrade for ONE campaign on its own branch."""
    rec = _recipe.current()
    wc = _clone_workcopy(entity, state_dir, git_runner)
    branch = f"mneme/adopt-{campaign}-{rec.version}"
    wc.checkout_branch(branch)
    _apply_to_workcopy(wc, campaign, rec)
    if wc.commit_all(f"mneme: adopt recipe {rec.version} for {campaign}"):
        wc.push(branch)
    return branch


def adopt_in_place(entity: ConfigEntity, campaign: str) -> tuple[list[Path], TargetConfig]:
    """Interactive confirmed adopt (FR-030): write the upgraded authority + re-rendered
    derived files **directly into the active checkout** for ONE campaign. Writes only
    mneme-managed files (never campaign content), and leaves them UNCOMMITTED for the
    human to review. Returns (written_paths, target_diff)."""
    rec = _recipe.current()
    ref = _discover.find(entity, campaign)
    if not ref.has_authority:
        raise _workcopy.WorkingCopyError(
            f"{campaign} has no .mneme/mempalace.yaml — bootstrap it first"
        )
    cfg = _authority.load(ref.path)
    diff = _target.resolve(cfg, rec)
    upgraded = replace(cfg, recipe_version=rec.version)
    written = [_authority.write(upgraded, ref.path)]
    written += _render.write_all(upgraded, rec, ref.path)
    return written, diff
