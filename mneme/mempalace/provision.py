"""Provision a campaign's dedicated store (003, D2).

mneme does not format a store itself — it points `mempalace mine` at the per-campaign
palace path (from the authority's store pointer) and lets the first mine *create* the
store (lowest coupling — Principle VIII). Wings are mined sub-scopes-before-root.
"""

from __future__ import annotations

from pathlib import Path

from hypostasis.models import ConfigEntity

from . import authority as _authority
from . import embedder_guard as _guard
from . import mine_record as _record
from .mine_report import SkipNotice, WingSkips
from .models import CampaignMempalaceConfig
from .runner import MempalaceError, MempalaceRunner


class FirstMine(tuple):
    """``(store_path, mined_wing_sources)`` — a 2-tuple for existing callers — that also
    carries ``.skips`` (GH #31): the (wing, SkipNotice) pairs mempalace reported."""

    skips: WingSkips
    record_warning: str | None

    def __new__(
        cls, store: Path, mined: list[str], skips: WingSkips = (), record_warning: str | None = None
    ):
        obj = super().__new__(cls, (store, mined))
        obj.skips = tuple(skips)
        obj.record_warning = record_warning
        return obj


def first_mine(
    cfg: CampaignMempalaceConfig,
    campaign_dir: Path,
    runner: MempalaceRunner,
    *,
    dry_run: bool = False,
    entity: ConfigEntity | None = None,
    prober: _guard.Prober | None = None,
) -> FirstMine:
    """Mine every wing into the campaign's dedicated store (creating it). Returns
    (store_path, mined-wing-sources) plus ``.skips``. The store pointer must be present
    (FR-013/016). With ``entity``, fails closed (GH #26) if the existing store's dimension
    mismatches/can't be verified against the declared embedder; ``entity=None`` skips it.
    GH #31: on a real, successful run the aggregated skips are recorded in the store."""
    store = _authority.require_store(cfg)
    _guard.require_writable(entity, store.path, prober)
    mined: list[str] = []
    wing_names: list[str] = []
    skips: list[tuple[str, SkipNotice]] = []
    for w in cfg.wings:  # authority order is sub-scopes-before-root (FR-004)
        wing_path = campaign_dir / w.source
        try:
            res = runner.mine(wing_path, palace=store.path, dry_run=dry_run)
        except MempalaceError as e:
            # GH #31: earlier wings' skips are real; never leave a stale "clean" record.
            e.skips = tuple(skips)
            if not dry_run:
                e.record_warning = _record.try_write(
                    store.path, cfg.campaign, wing_names, tuple(skips),
                    status="failed", error=str(e),
                )
            raise
        mined.append(w.source or ".")
        wing_names.append(w.name)
        skips.extend((w.name, n) for n in (getattr(res, "skips", None) or ()))
    warn = None
    if not dry_run:
        warn = _record.try_write(store.path, cfg.campaign, wing_names, tuple(skips))
    return FirstMine(store.path, mined, tuple(skips), warn)
