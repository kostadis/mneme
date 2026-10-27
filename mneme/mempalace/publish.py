"""Publish a recipe upgrade (US3, FR-009/010/018) and per-campaign adopt (FR-021).

`preview` computes, per campaign, exactly what an upgrade would change (writes
nothing). `publish` writes the upgrade for every campaign into the private working
copy and pushes a proposal branch — never the active checkout. `adopt` is the
manual per-campaign gate: it stages the upgrade for one campaign on its own branch.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from hypostasis import config as _config
from hypostasis.models import ConfigEntity
from mneme.corpus.config import corpus_path, has_corpus

from . import authority as _authority
from . import discover as _discover
from . import recipe as _recipe
from . import render as _render
from . import target as _target
from . import workcopy as _workcopy
from .corpus_guard import (
    MOVE_CODES,
    CorpusRefusal,
    MoveRefused,
    migrate_shadowed,
    move_shadowed_text,
)
from .discover import campaigns_roots
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


def preview(entity: ConfigEntity, rec=None) -> list[CampaignPlan]:
    """Per-campaign upgrade plan against ``rec`` (default: the current recipe). Writes nothing."""
    rec = rec or _recipe.current()
    plans: list[CampaignPlan] = []
    for ref in _discover.discover(entity):
        if not ref.has_authority:
            continue
        try:
            cfg = _authority.load(ref.path, mempalace_root=_config.mempalace_root(entity))
        except _authority.AuthorityError:
            continue
        target = _target.resolve(cfg, rec)
        if has_corpus(ref.path):
            try:
                if mig := move_shadowed_text(ref.path, rec):
                    note = f"corpus.yaml: {', '.join(mig[1])} moves from campaign_kinds to kinds"
                    target = replace(target, changed=(*target.changed, note))
            except MoveRefused as e:
                target = replace(target, conflicts=(*target.conflicts, str(e)))
        plans.append(CampaignPlan(ref.name, target))
    return plans


def planned_move(entity: ConfigEntity, campaign: str, rec=None) -> tuple[list[str], str | None]:
    """``(kinds that adopting would move to `kinds:`, why it would refuse or None)``.
    Writes nothing."""
    rec = rec or _recipe.current()
    ref = _discover.resolve(entity, campaign)
    if not has_corpus(ref.path):
        return [], None
    try:
        mig = move_shadowed_text(ref.path, rec)
    except MoveRefused as e:
        return [], str(e)
    return (mig[1] if mig else []), None


def _managed_paths(cfg, rec, camp_dir: Path) -> list[Path]:
    """Every file an adopt may create, change or remove for this campaign."""
    paths: set[Path] = {p for p in (camp_dir / ".mneme").rglob("*") if p.is_file()}
    if has_corpus(camp_dir):
        paths |= {camp_dir / "mempalace.yaml", camp_dir / ".gitignore",
                  camp_dir / ".mneme" / "corpus.yaml"}
        paths |= {camp_dir / r for r in _render.leftover_wing_renders(camp_dir)}
    else:
        paths |= {camp_dir / a.target for a in _render.render(cfg, rec)}
    paths.add(_authority.authority_path(camp_dir))
    return sorted(paths)


def _restore(saved: dict[Path, bytes | None]) -> None:
    for path, data in saved.items():
        if data is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)


def _upgrade(cfg, rec, camp_dir: Path):
    """The authority with only `recipe_version` moved. A corpus campaign's authority never
    gains `wings:` or `extra_exclusions:` (007 T042, FR-001a)."""
    upgraded = replace(cfg, recipe_version=rec.version)
    if has_corpus(camp_dir):
        upgraded = replace(upgraded, wings=(), extra_exclusions=())
    return upgraded


def _migrated_corpus(
    command: str, campaign: str, camp_dir: Path, rec
) -> tuple[str, list[str]] | None:
    """The corpus.yaml rewrite adopting ``rec`` implies (kinds ``rec`` made standard move out of
    `campaign_kinds:`), or None. Refuses, writing nothing, when the move cannot be made."""
    if not has_corpus(camp_dir):
        return None
    return migrate_shadowed(command, campaign, camp_dir, rec)


def _apply_to_workcopy(wc: _workcopy.WorkingCopy, campaign: str, rec) -> None:
    """Write the (migrated) corpus.yaml, the upgraded authority and the re-rendered derived
    files for one campaign. corpus.yaml goes first: the render hashes it."""
    camp_dir = wc.path / campaign
    cfg = _authority.load(camp_dir)
    migrated = _migrated_corpus("adopt/publish", campaign, camp_dir, rec)  # before any write
    if migrated:
        corpus_path(camp_dir).write_text(migrated[0])
    upgraded = _upgrade(cfg, rec, camp_dir)
    _authority.write(upgraded, camp_dir)
    _render.write_all(upgraded, rec, camp_dir)


def _campaigns_tree(entity: ConfigEntity, root: Path | None = None) -> Path:
    """Resolve the single tree a workcopy operation targets (005, FR-009).

    An explicit ``root`` (e.g. a campaign's own tree) wins. Otherwise, with one declared
    tree, use it (unchanged behavior); with several, refuse rather than guess — publish/
    adopt are per-tree, so the caller must say which."""
    if root is not None:
        return Path(root)
    roots = campaigns_roots(entity)
    if len(roots) > 1:
        raise _workcopy.WorkingCopyError(
            "multiple campaigns trees declared — publish/adopt target one tree at a time; "
            f"declared: {', '.join(str(r) for r in roots)}"
        )
    return roots[0]


def _clone_workcopy(
    entity: ConfigEntity, state_dir: Path | None, runner, root: Path | None = None
) -> _workcopy.WorkingCopy:
    git_runner = runner or _workcopy._run_git
    tree = _campaigns_tree(entity, root)
    remote = _workcopy.origin_url(tree, runner=git_runner)
    if not remote:
        raise _workcopy.WorkingCopyError(
            f"campaigns tree {tree} has no git origin — cannot publish through version control"
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
    plans = preview(entity, rec)  # the same recipe that is applied below
    wc = _clone_workcopy(entity, state_dir, git_runner)
    branch = f"mneme/recipe-{rec.version}"
    wc.checkout_branch(branch)
    for plan in plans:
        if any(c.split(":")[0] in MOVE_CODES for c in plan.target.conflicts):
            continue  # reported in the plan line; never written
        try:
            _apply_to_workcopy(wc, plan.campaign, rec)
        except Exception:
            wc.abandon(branch)  # nothing committed or pushed; leave no half-staged branch
            raise
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
    ref = _discover.resolve(entity, campaign)  # 005 — adopt targets the campaign's own tree
    _migrated_corpus("adopt", campaign, ref.path, rec)  # early fail, before cloning anything
    wc = _clone_workcopy(entity, state_dir, git_runner, root=ref.tree)
    branch = f"mneme/adopt-{campaign}-{rec.version}"
    wc.checkout_branch(branch)
    try:
        # The clone is what is committed, and it can differ from the live checkout (the corpus
        # may have changed on origin), so the check is repeated there.
        _apply_to_workcopy(wc, campaign, rec)
    except Exception:
        wc.abandon(branch)  # nothing committed or pushed; leave no half-staged branch
        raise
    if wc.commit_all(f"mneme: adopt recipe {rec.version} for {campaign}"):
        wc.push(branch)
    return branch


def adopt_in_place(entity: ConfigEntity, campaign: str) -> tuple[list[Path], TargetConfig]:
    """Interactive confirmed adopt (FR-030): write the upgraded authority + re-rendered
    derived files **directly into the active checkout** for ONE campaign. Writes only
    mneme-managed files (never campaign content), and leaves them UNCOMMITTED for the
    human to review. Returns (written_paths, target_diff)."""
    rec = _recipe.current()
    ref = _discover.resolve(entity, campaign)
    if not ref.has_authority:
        raise _workcopy.WorkingCopyError(
            f"{campaign} has no .mneme/mempalace.yaml — bootstrap it first"
        )
    cfg = _authority.load(ref.path, mempalace_root=_config.mempalace_root(entity))
    diff = _target.resolve(cfg, rec)
    migrated = _migrated_corpus("adopt", campaign, ref.path, rec)  # before any write
    upgraded = _upgrade(cfg, rec, ref.path)
    saved = {p: (p.read_bytes() if p.exists() else None)
             for p in _managed_paths(cfg, rec, ref.path)}
    try:
        written: list[Path] = []
        if migrated:
            corpus_path(ref.path).write_text(migrated[0])
            written.append(corpus_path(ref.path))
        written.append(_authority.write(upgraded, ref.path))
        written += _render.write_all(upgraded, rec, ref.path)
    except BaseException:
        _restore(saved)  # all or nothing: never leave corpus.yaml moved with a stale render
        raise
    return written, diff
