"""Honest per-campaign conformance (US2, FR-005/008/027 — Principle I).

Reports observed state from the silicon: render-stamp coherence, the `mempalace`
source-vs-index drift signal, and the authority-vs-recipe comparison paired with the
human's recorded dispositions. A deliberate, recorded divergence is NOT a failure;
an undispositioned one is "needs a decision" and IS (FR-027). mneme never guesses
*why* a campaign diverges — it reads the recorded reason or flags its absence.
"""

from __future__ import annotations

import re
from pathlib import Path

from hypostasis.models import ConfigEntity
from mneme.corpus import compare as _compare
from mneme.corpus import config as _cconfig
from mneme.corpus import resolve as _cresolve
from mneme.corpus import toc as _toc
from mneme.corpus.config import has_corpus

from . import authority as _authority
from . import corpus_record as _crec
from . import discover as _discover
from . import former_wings as _former
from . import mine_record as _record
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


def _recipe_row(
    cfg: CampaignMempalaceConfig, recipe: Recipe, *, corpus: bool = False
) -> ConformanceRow:
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
    if not corpus and not _scaffold_matches(cfg, recipe):  # a corpus campaign has no wings
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


def sync_scope(ref: CampaignRef, cfg) -> tuple[Path, list[Path]]:
    """(palace, extra `--root`s) for `mempalace sync` against this campaign's own store.

    Shared by the `index` status row and `mneme mp prune` so the check and the deletion can
    never look at different scopes (Principle I). Roots: every legitimate source root — the
    campaign plus each wing's dir (as provision mines them); the campaign itself is `path`."""
    roots = [ref.path / w.source for w in cfg.wings]
    extra = [r for r in dict.fromkeys(roots) if r.resolve() != ref.path.resolve()]
    return cfg.store.path, extra


def _index_row(ref: CampaignRef, cfg, runner: MempalaceRunner) -> ConformanceRow:
    """GH #22 — orphaned-drawer check against the CAMPAIGN's store (Principle I: unknown is
    reported as unknown). New/changed sources are not detectable via the mempalace CLI."""
    if cfg.store is None:
        return ConformanceRow(
            ref.name, "index", State.INDEX_UNVERIFIED,
            note="no store pointer — index not checked (won't query an unknown palace)",
        )
    palace, extra = sync_scope(ref, cfg)
    chk = runner.is_stale(ref.path, palace=palace, roots=extra)
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
                f"{chk.gitignored} gitignored) — preview with `mneme mp prune {ref.name}`, "
                "then `--confirm`"
            )
        if chk.out_of_scope:
            parts.append(
                f"{chk.out_of_scope} drawers point outside the campaign's sources "
                "(moved campaign or foreign store?) — run "
                f"`mneme mp regenerate {ref.name} --confirm`"
            )
        return ConformanceRow(ref.name, "index", State.STALE, note="; ".join(parts))
    return ConformanceRow(
        ref.name, "index", State.BUILT,
        note="no orphaned drawers (new/changed files are not detected)",
    )


_SHOWN = 10  # files named per finding in a status note (display only; the data is complete)

_CODE_STATE = {
    _compare.INVALID: State.CORPUS_INVALID,
    _compare.UNKNOWN: State.CORPUS_UNKNOWN,
    _compare.MISSING: State.CORPUS_MISSING,
    _compare.UNDECLARED: State.UNDECLARED_DRAWERS,
    _compare.OUT_OF_SCOPE: State.OUT_OF_SCOPE,
    _compare.UNMINED: State.UNMINED,
    _compare.STALE: State.CORPUS_STALE,
    _compare.WRONG_WING: State.WRONG_WING,
    _compare.TOC_STALE: State.TOC_STALE,
}


def _finding_text(f: _compare.CorpusFinding, campaign: str) -> str:
    names = ", ".join(f.files[:_SHOWN])
    more = f" (+{len(f.files) - _SHOWN} more)" if len(f.files) > _SHOWN else ""
    head = f.code.upper()
    if f.code in (_compare.INVALID, _compare.UNKNOWN):
        body = "; ".join(f.files[:_SHOWN]) + more
    elif f.code == _compare.TOC_STALE:
        body = f.detail
    else:
        drawers = f" ({f.drawers} drawers)" if f.drawers else ""
        body = f"{f.count} file(s){drawers}: {names}{more}"
        if f.detail:
            body += f" [{f.detail}]"
    remedy = f.remedy
    if re.fullmatch(r"mneme mp \w+", remedy):
        remedy += f" {campaign}"
    return f"{head}: {body} -> {remedy}"


def _corpus_findings(ref, cfg, rec, runner) -> _compare.CorpusFindings:
    """Resolve the declaration fresh and compare it with the palace. Never raises: whatever
    cannot be read is a finding (invalid / unknown), never a silent OK (FR-017)."""
    try:
        ccfg = _cconfig.load(ref.path, rec)
    except _cconfig.CorpusConfigError as e:
        return _compare.CorpusFindings((_compare.CorpusFinding(
            _compare.INVALID, tuple(f.line() for f in e.findings),
            remedy="edit .mneme/corpus.yaml (`mneme corpus check`)",
        ),), verified=False)
    resolved = _cresolve.resolve(ccfg, ref.path, rec)
    toc_check = _toc.verify(ref.path, _toc.build(resolved, ccfg, rec))
    sources = None
    why = None
    if cfg.store is None:
        why = "no store pointer, so the palace cannot be read"
    elif not Path(cfg.store.path).is_dir():
        why = "the store is not provisioned (`mneme mp bringup`)"
    elif not runner.supports_corpus():
        why = "this mempalace lacks the corpus verbs (`sources`, `forget`, `mine --files-from`)"
    else:
        sources = runner.sources(cfg.store.path)
        if sources is None:
            why = "`mempalace sources` failed or returned unparseable output"
    record = None
    rec_err = None
    if cfg.store is not None:
        try:
            record = _crec.read(cfg.store.path)
        except _crec.CorpusRecordError as e:
            rec_err = str(e)
    return _compare.compare(
        resolved, sources, record, toc_check, ref.path,
        record_error=rec_err, sources_error=why,
    )


def _corpus_rows(ref, cfg, rec, runner) -> tuple[ConformanceRow, ConformanceRow]:
    """007 US2: the `corpus` row, and the `index` row derived from the SAME comparison
    (a corpus campaign's `sync --dry-run` scope would be a different question)."""
    res = _corpus_findings(ref, cfg, rec, runner)
    if res.ok:
        corpus = ConformanceRow(
            ref.name, "corpus", State.CONFORMANT,
            note="palace equals the declared corpus; every drawer is current",
        )
    else:
        corpus = ConformanceRow(
            ref.name, "corpus", _CODE_STATE[res.findings[0].code],
            observed=",".join(res.codes),
            note=" | ".join(_finding_text(f, ref.name) for f in res.findings),
        )
    drawer_codes = {_compare.UNDECLARED, _compare.OUT_OF_SCOPE, _compare.UNMINED,
                    _compare.STALE, _compare.WRONG_WING, _compare.MISSING}
    if not res.verified:
        index = ConformanceRow(
            ref.name, "index", State.INDEX_UNVERIFIED,
            note="unverified: the corpus comparison could not read the palace",
        )
    elif any(c in drawer_codes for c in res.codes):
        index = ConformanceRow(
            ref.name, "index", State.STALE,
            note="palace differs from the corpus — see the corpus row",
        )
    else:
        index = ConformanceRow(
            ref.name, "index", State.BUILT, note="palace drawer sources equal the corpus",
        )
    return corpus, index


def _gaps_row(ref: CampaignRef, cfg) -> ConformanceRow | None:
    """GH #31 — files the LAST mneme-run mine skipped (Principle I: unknown is not green).
    Only for campaigns with a store pointer; reads the record in the store folder."""
    if cfg.store is None:
        return None
    try:
        rec = _record.read(cfg.store.path)
    except _record.MineRecordError as e:
        return ConformanceRow(ref.name, "gaps", State.INDEX_UNVERIFIED, note=str(e))
    if rec is None:
        return ConformanceRow(
            ref.name, "gaps", State.INDEX_UNVERIFIED,
            note=f"no mine recorded by mneme yet — run `mneme mp refresh {ref.name}` "
            "to record skipped files",
        )
    names = rec.names
    carried = " (carried over by restore)" if rec.carried_over else ""
    if rec.status == "failed":
        partial = ", ".join(names[:_GAPS_SHOWN]) or "none"
        return ConformanceRow(
            ref.name, "gaps", State.INDEX_UNVERIFIED,
            note=f"last mine failed at {rec.mined_at}: {rec.error}; partial skips: {partial}"
            f"{carried}",
        )
    if not names:
        return ConformanceRow(
            ref.name, "gaps", State.CONFORMANT,
            note=f"no files skipped at last mine ({rec.mined_at}){carried}",
        )
    shown = ", ".join(names[:_GAPS_SHOWN])
    more = f" (+{len(names) - _GAPS_SHOWN} more)" if len(names) > _GAPS_SHOWN else ""
    return ConformanceRow(
        ref.name, "gaps", State.INDEX_GAPS, observed=str(len(names)),
        note=f"{len(names)} file(s) skipped at last mine: {shown}{more}{carried}",
    )


_GAPS_SHOWN = 5


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

    corpus = has_corpus(ref.path)
    rows = [_recipe_row(cfg, recipe, corpus=corpus)]
    if entity is not None and not corpus and (warn := _former.try_record(cfg)):
        rows.append(ConformanceRow(ref.name, "former-wings", State.CONFORMANT, note=warn))

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

    if corpus:
        rows.extend(_corpus_rows(ref, cfg, rec, runner))
    elif check_index:
        rows.append(_index_row(ref, cfg, runner))
    rows.extend(_store_backup_rows(ref, cfg, entity, runner, prober))
    if entity is not None and (gaps := _gaps_row(ref, cfg)) is not None:
        rows.append(gaps)
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
    from mneme.corpus.config import CORPUS_REFUSAL

    from . import authority as _auth
    from .discover import CampaignRef, _existing_wing_dirs

    cdir = Path(campaign_dir)
    if has_corpus(cdir):
        # 007: wing_dirs of a corpus campaign is its root; a wing-model check would be a lie.
        return ConformanceReport(rows=(
            ConformanceRow(cdir.name, "recipe", State.INVALID_CONFIG, note=CORPUS_REFUSAL),
        ))
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

