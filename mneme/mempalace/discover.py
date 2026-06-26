"""Discover the campaigns mneme manages (FR-001).

Enumerates campaign workspaces under ``data_roots.campaigns`` (never a hardcoded
list), and for each reports whether a `.mneme/` authority is present and which
existing wing dirs (those containing a `mempalace.yaml`) are minable. Reads observe
the live active checkout (FR-019).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hypostasis.models import ConfigEntity

from . import authority as _authority


class DiscoveryError(Exception):
    """No campaigns root configured."""


@dataclass(frozen=True)
class CampaignRef:
    name: str
    path: Path
    has_authority: bool
    wing_dirs: tuple[Path, ...]  # dirs with a mempalace.yaml, for mining


def campaigns_root(entity: ConfigEntity) -> Path:
    root = entity.data_roots.get("campaigns")
    if root is None:
        raise DiscoveryError("hypostasis.yaml has no data_roots.campaigns")
    return Path(root).expanduser()


def _existing_wing_dirs(campaign_dir: Path) -> tuple[Path, ...]:
    """Dirs under the campaign that contain a `mempalace.yaml` (existing wings)."""
    found = [p.parent for p in campaign_dir.rglob("mempalace.yaml")]
    # Exclude the mneme authority itself (.mneme/mempalace.yaml is NOT a wing).
    found = [d for d in found if d.name != ".mneme"]
    return tuple(sorted(found, key=lambda d: len(d.relative_to(campaign_dir).parts), reverse=True))


def discover(entity: ConfigEntity) -> list[CampaignRef]:
    """Every immediate subdirectory of the campaigns root is a campaign."""
    root = campaigns_root(entity)
    if not root.is_dir():
        raise DiscoveryError(f"campaigns root not found: {root}")
    refs: list[CampaignRef] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        refs.append(
            CampaignRef(
                name=child.name,
                path=child,
                has_authority=_authority.has_authority(child),
                wing_dirs=_existing_wing_dirs(child),
            )
        )
    return refs


def find(entity: ConfigEntity, campaign: str) -> CampaignRef:
    root = campaigns_root(entity)
    cdir = root / campaign
    if not cdir.is_dir():
        raise DiscoveryError(f"campaign workspace not found: {cdir}")
    return CampaignRef(
        name=campaign,
        path=cdir,
        has_authority=_authority.has_authority(cdir),
        wing_dirs=_existing_wing_dirs(cdir),
    )
