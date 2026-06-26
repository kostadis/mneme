"""Provision a campaign's dedicated store (003, D2).

mneme does not format a store itself — it points `mempalace mine` at the per-campaign
palace path (from the authority's store pointer) and lets the first mine *create* the
store (lowest coupling — Principle VIII). Wings are mined sub-scopes-before-root.
"""

from __future__ import annotations

from pathlib import Path

from . import authority as _authority
from .models import CampaignMempalaceConfig
from .runner import MempalaceRunner


def first_mine(
    cfg: CampaignMempalaceConfig,
    campaign_dir: Path,
    runner: MempalaceRunner,
    *,
    dry_run: bool = False,
) -> tuple[Path, list[str]]:
    """Mine every wing into the campaign's dedicated store (creating it). Returns
    (store_path, mined-wing-sources). The store pointer must be present (FR-013/016)."""
    store = _authority.require_store(cfg)
    mined: list[str] = []
    for w in cfg.wings:  # authority order is sub-scopes-before-root (FR-004)
        wing_path = campaign_dir / w.source
        runner.mine(wing_path, palace=store.path, dry_run=dry_run)
        mined.append(w.source or ".")
    return store.path, mined
