"""Refresh campaign indexes from each campaign's own configuration (US1, FR-003/004).

Orchestrates `mempalace mine` per wing in sub-scopes-before-root order, using the
wings the campaign already has. A campaign with no wings is *skipped* (not failed);
a campaign whose mining fails is isolated so the run continues for the others
(FR-006). Mining is idempotent (FR-014). Reads the live active checkout (FR-019);
writes only the index, never the campaign repo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from hypostasis import config as _config
from hypostasis.models import ConfigEntity

from . import authority as _authority
from . import discover as _discover
from . import embedder_guard as _guard
from . import mine_record as _record
from .discover import CampaignRef
from .mine_report import WingSkips, warning_lines
from .runner import MempalaceError, MempalaceRunner


@dataclass
class RefreshResult:
    campaign: str
    wings: list[str] = field(default_factory=list)  # rel paths mined (or planned)
    skipped: bool = False
    failed: bool = False
    error: str = ""
    dry_run: bool = False
    skips: WingSkips = ()  # GH #31: (wing, notice) pairs from this mine
    record_warning: str | None = None

    def warnings(self) -> list[str]:
        """GH #31: one `WARN index gap` line per skipped file (never changes the outcome)."""
        lines = warning_lines(self.campaign, self.skips)
        if self.record_warning:
            lines.append(self.record_warning)
        return lines

    def line(self) -> str:
        if self.skipped:
            return f"{self.campaign:24} SKIP   {self.error or 'no wings configured'}"
        if self.failed:
            return f"{self.campaign:24} FAIL   {self.error}"
        verb = "PLAN" if self.dry_run else "OK"
        return f"{self.campaign:24} {verb:6} mined: {', '.join(self.wings) or '(none)'}"


def _guard_store(ref: CampaignRef, entity: ConfigEntity, prober):
    """GH #26: resolve the campaign's store and refuse to extend an existing palace whose dim
    mismatches the embedder. FAILS CLOSED: unloadable authority / no store pointer ⇒
    MempalaceError (we cannot name, hence cannot verify, the palace being mined)."""
    try:
        cfg = _authority.load(ref.path, mempalace_root=_config.mempalace_root(entity))
    except _authority.AuthorityError as e:
        raise MempalaceError(f"authority unloadable ({'; '.join(e.problems)})") from None
    if cfg.store is None:
        raise MempalaceError(
            "authority has no store pointer — cannot verify the palace; run `mneme mp bringup`"
        )
    _guard.require_writable(entity, cfg.store.path, prober)
    return cfg


def _refresh_one(
    ref: CampaignRef,
    runner: MempalaceRunner,
    dry_run: bool,
    entity: ConfigEntity | None = None,
    prober=None,
) -> RefreshResult:
    result = RefreshResult(campaign=ref.name, dry_run=dry_run)
    if not ref.wing_dirs:
        result.skipped = True
        return result
    store: Path | None = None
    names: dict[str, str] = {}  # wing source -> wing name (for the GH #31 record)
    if entity is not None and not ref.has_authority:
        # spec 002 US1: no configuration ⇒ skipped (not failed, not mined).
        result.skipped = True
        result.error = "no mneme authority — run `mneme mp bootstrap`/`migrate`"
        return result
    if entity is not None:
        try:
            cfg = _guard_store(ref, entity, prober)
            store = cfg.store.path
            names = {(w.source or "."): w.name for w in cfg.wings}
        except MempalaceError as e:
            result.failed = True
            result.error = str(e)
            return result
    # discover returns wing dirs deepest-first → sub-scopes before root (FR-004).
    skips: list = []
    wing_names: list[str] = []
    for wing_dir in ref.wing_dirs:
        rel = str(wing_dir.relative_to(ref.path)) or "."
        wing = names.get(rel, rel)
        try:
            res = runner.mine(wing_dir, palace=store, dry_run=dry_run)
            result.wings.append(rel)
            wing_names.append(wing)
            skips.extend((wing, n) for n in (getattr(res, "skips", None) or ()))
        except MempalaceError as e:
            result.failed = True
            result.error = str(e)
            result.skips = tuple(skips)  # earlier wings' skips are still real
            if store is not None and not dry_run:  # no stale "clean" record behind a failure
                result.record_warning = _record.try_write(
                    store, ref.name, wing_names, result.skips, status="failed", error=str(e)
                )
            return result
    result.skips = tuple(skips)
    if store is not None and not dry_run:  # GH #31: remember this mine's gaps for `mp status`
        result.record_warning = _record.try_write(store, ref.name, wing_names, result.skips)
    return result


def refresh(
    entity: ConfigEntity,
    campaign: str | None = None,
    *,
    campaign_dir: str | None = None,
    dry_run: bool = False,
    runner: MempalaceRunner | None = None,
    verbose: bool = False,
    prober: _guard.Prober | None = None,
) -> list[RefreshResult]:
    """Refresh one campaign (``campaign``/``campaign_dir`` set) or all (both None)."""
    runner = runner or MempalaceRunner.for_entity(entity, stream=verbose)
    if campaign or campaign_dir:
        refs = [_discover.resolve(entity, campaign, campaign_dir)]
    else:
        refs = _discover.discover(entity)
    return [_refresh_one(ref, runner, dry_run, entity, prober) for ref in refs]

