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
from .models import CampaignMempalaceConfig
from .runner import MempalaceRunner


def first_mine(
    cfg: CampaignMempalaceConfig,
    campaign_dir: Path,
    runner: MempalaceRunner,
    *,
    dry_run: bool = False,
    entity: ConfigEntity | None = None,
    prober: _guard.Prober | None = None,
) -> tuple[Path, list[str]]:
    """Mine every wing into the campaign's dedicated store (creating it). Returns
    (store_path, mined-wing-sources). The store pointer must be present (FR-013/016).
    With ``entity``, fails closed (GH #26) if the existing store's dimension
    mismatches/can't be verified against the declared embedder; ``entity=None`` skips it."""
    store = _authority.require_store(cfg)
    _guard.require_writable(entity, store.path, prober)
    mined: list[str] = []
    for w in cfg.wings:  # authority order is sub-scopes-before-root (FR-004)
        wing_path = campaign_dir / w.source
        runner.mine(wing_path, palace=store.path, dry_run=dry_run)
        mined.append(w.source or ".")
    return store.path, mined
