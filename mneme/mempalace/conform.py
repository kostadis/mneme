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
from . import ownership as _ownership
from . import recipe as _recipe
from . import render as _render
from .authority import AuthorityError
from .discover import CampaignRef
from .models import (
    FAIL_STATES,
    CampaignMempalaceConfig,
    ConformanceReport,
    ConformanceRow,
    Recipe,
    State,
)
from .recipe import RecipeError
from .runner import MempalaceRunner


def _mp_root(entity):
    """This host's palace root, or None when status runs without an entity (check_dir)."""
    from hypostasis import config as _config

    return _config.mempalace_root(entity) if entity is not None else None

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


def _embedder_row(ref, cfg, entity, prober) -> ConformanceRow | None:
    """GH #26b — built vs effective embedding dimension (Principle I: unknown is not green).
    No row when the store dir doesn't exist (the `store` row already says not provisioned)."""
    from . import embedder_guard as _guard

    if not cfg.store.path.is_dir():
        return None
    r = _guard.check(entity, cfg.store.path, prober)
    if r.state is _guard.GuardState.MISMATCH:
        return ConformanceRow(
            ref.name, "embedder", State.EMBEDDER_MISMATCH, observed=str(r.built or ""),
            expected=str(r.expected or ""), note=r.message,
        )
    if r.state is _guard.GuardState.UNKNOWN:
        return ConformanceRow(
            ref.name, "embedder", State.EMBEDDER_UNVERIFIED, observed=str(r.built or ""),
            note=r.message,
        )
    return ConformanceRow(ref.name, "embedder", State.CONFORMANT, note=r.message)


def _store_backup_rows(ref, cfg, entity, runner, prober=None) -> list[ConformanceRow]:
    """003: per-campaign store + backup dimensions (Principle IX), only when the
    authority carries a store pointer and we have the entity (skipped for check_dir)."""
    from hypostasis import config as _config

    from . import backup as _backup
    from . import bringup as _bringup
    from . import health as _health
    from .models import StoreState

    if entity is None or cfg.store is None:
        return []
    rows: list[ConformanceRow] = []
    h = _health.health(cfg.store.path, runner=runner)
    if h.state is StoreState.HEALTHY:
        rows.append(ConformanceRow(ref.name, "store", State.BUILT, note="store healthy"))
    elif h.state is StoreState.DEGRADED:
        rows.append(ConformanceRow(ref.name, "store", State.STALE_RENDER, note=h.note))
    else:  # missing — not a hard fail; it's a to-do (run bringup)
        rows.append(
            ConformanceRow(
                ref.name, "store", State.MISSING_CONFIG, note="not provisioned — `mneme mp bringup`"
            )
        )
    emb = _embedder_row(ref, cfg, entity, prober)
    if emb is not None:
        rows.append(emb)
    b = _backup.latest_backup(entity, ref.name)
    rows.append(
        ConformanceRow(
            ref.name, "backup", State.CONFORMANT, note=f"backup: {b.name}" if b else "no backup"
        )
    )
    # US5/SC-008: the store-naming faces (CLI pointer + MCP) must agree on the store.
    # Resolved per host (006) — each host's faces name that host's root, which is sound
    # precisely because config.json and .mcp.json are not tracked in the campaign repo.
    config_json = _bringup.default_config_json(_config.mempalace_root(entity))
    mism = _render.faces_coherent(cfg, ref.path, config_json, entity.env)
    if mism:
        rows.append(ConformanceRow(ref.name, "faces", State.STALE_RENDER, note="; ".join(mism)))
    else:
        rows.append(
            ConformanceRow(ref.name, "faces", State.CONFORMANT, note="right store everywhere")
        )
    return rows


def _membership_row(ref: CampaignRef, entity=None) -> ConformanceRow:
    """005 — report the campaign's ownership vs this mneme (Principle IX). Read-only."""
    identity = entity.mneme_identity if entity is not None else None
    state = _ownership.classify(ref.path, identity)
    if state is _ownership.OwnerState.OWNED:
        return ConformanceRow(ref.name, "owner", State.OWNED, note="owned by this mneme")
    if state is _ownership.OwnerState.FOREIGN:
        owner = _ownership.read_owner(ref.path)
        fid = owner.mneme_id if owner else "?"
        return ConformanceRow(
            ref.name, "owner", State.FOREIGN, observed=fid,
            note=f"owned by a different mneme ({fid}) — decide before managing",
        )
    if state is _ownership.OwnerState.UNVERIFIABLE:
        return ConformanceRow(
            ref.name, "owner", State.UNVERIFIABLE,
            note="fleet identity not established — `mneme identity show` names the choice "
                 "(adopt an existing fleet, or mint a new one)",
        )
    return ConformanceRow(
        ref.name, "owner", State.UNINTEGRATED,
        note="discovered, not integrated (run `mneme integrate`)",
    )


def _index_row(ref: CampaignRef, cfg, runner: MempalaceRunner) -> ConformanceRow:
    """GH #22 — orphaned-drawer check against the CAMPAIGN's store (Principle I: unknown is
    reported as unknown). New/changed sources are not detectable via the mempalace CLI."""
    if cfg.store is None:
        return ConformanceRow(
            ref.name, "index", State.INDEX_UNVERIFIED,
            note="no store pointer — index not checked (won't query an unknown palace)",
        )
    # every legitimate source root: the campaign plus each wing's dir (as provision mines them)
    roots = [ref.path / w.source for w in cfg.wings]
    extra = [r for r in dict.fromkeys(roots) if r.resolve() != ref.path.resolve()]
    chk = runner.is_stale(ref.path, palace=cfg.store.path, roots=extra)
    if chk.stale is None:
        return ConformanceRow(
            ref.name, "index", State.INDEX_UNVERIFIED, note=f"unverified: {chk.reason}"
        )
    if chk.stale:
        parts = []
        n = chk.missing + chk.gitignored
        if n:
            parts.append(
                f"index has {n} orphaned drawers ({chk.missing} missing, "
                f"{chk.gitignored} gitignored) — run `mneme mp refresh`"
            )
        if chk.out_of_scope:
            parts.append(
                f"{chk.out_of_scope} drawers point outside the campaign's sources "
                "(moved campaign or foreign store?) — run `mneme mp regenerate`"
            )
        return ConformanceRow(ref.name, "index", State.STALE, note="; ".join(parts))
    return ConformanceRow(
        ref.name, "index", State.BUILT,
        note="no orphaned drawers (new/changed files are not detected)",
    )


def _campaign_rows(
    ref: CampaignRef, recipe: Recipe, runner: MempalaceRunner, entity=None, prober=None,
    *, mp_root=None, check_index: bool = True,
) -> list[ConformanceRow]:
    if not ref.has_authority:
        return [
            ConformanceRow(
                ref.name, "recipe", State.MISSING_CONFIG,
                note="no .mneme/mempalace.yaml — skipped (run `mneme mp bootstrap`)",
            ),
            _membership_row(ref, entity),
        ]
    try:
        cfg = _authority.load(ref.path, mempalace_root=mp_root or _mp_root(entity))
    except AuthorityError as e:
        # FR-014a — one unloadable campaign is ONE bad row, never a wedged fleet run
        # (Principle VI). Its other dimensions are unknowable until the authority loads.
        return [
            ConformanceRow(
                ref.name, "recipe", State.INVALID_CONFIG,
                note="; ".join(e.problems) + " — other dimensions not reported until this is fixed",
            ),
            _membership_row(ref, entity),
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

    if check_index:
        rows.append(_index_row(ref, cfg, runner))
    rows.extend(_store_backup_rows(ref, cfg, entity, runner, prober))
    if _authority.has_legacy_store_path(ref.path):
        # FR-013 — it agrees with the derived location (a conflict would have failed the
        # load), so this is owed cleanup, not breakage. Surfacing it is the point: the
        # operator can't remove a field they were never told about (Principle IX).
        rows.append(
            ConformanceRow(
                ref.name, "authority", State.STALE_RENDER,
                note="legacy store.path — host-local, no longer tracked: remove the `path:` "
                     "key under `store:` in .mneme/mempalace.yaml and commit",
            )
        )
    rows.append(_membership_row(ref, entity))
    return rows


def check_dir(
    campaign_dir, *, runner: MempalaceRunner | None = None, entity=None,
    check_index: bool = True,
) -> ConformanceReport:
    """Conformance of a campaign at an arbitrary path (e.g. a working copy) — used by
    post-migration verification (FR-026) where the dir is not the active checkout.

    `entity` only resolves THIS host's palace root (store path derivation, GH #22); it does
    not enable the store/backup/faces rows. `check_index=False` skips the orphaned-drawer
    sync check: a working copy's path is not the path drawers were mined from, so sync
    against it would report everything out-of-scope (a misleading STALE)."""
    from pathlib import Path

    from hypostasis import config as _config

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
    root = _config.mempalace_root(entity) if entity is not None else None
    return ConformanceReport(
        rows=tuple(_campaign_rows(ref, rec, runner, mp_root=root, check_index=check_index))
    )


def report(
    entity: ConfigEntity,
    campaign: str | None = None,
    *,
    campaign_dir: str | None = None,
    runner: MempalaceRunner | None = None,
    prober=None,
) -> ConformanceReport:
    recipe = _recipe.current()
    runner = runner or MempalaceRunner.for_entity(entity)
    if campaign or campaign_dir:
        refs = [_discover.resolve(entity, campaign, campaign_dir)]
    else:
        refs = _discover.discover(entity)
    rows: list[ConformanceRow] = []
    for ref in refs:
        rows.extend(_campaign_rows(ref, recipe, runner, entity, prober))
    return ConformanceReport(rows=tuple(rows))


def format_row(row: ConformanceRow) -> str:
    if row.state in FAIL_STATES:
        flag = "FAIL"
    elif not row.ok:
        flag = "??  "  # unverified: not ok, but not a (non-strict) failure
    else:
        flag = "ok  "
    return f"{flag} {row.campaign:20} {row.dimension:7} {row.state.value:26} {row.note}"

