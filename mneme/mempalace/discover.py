"""Discover the campaigns mneme manages across one or more trees (005, FR-001/003).

``data_roots.campaigns`` is one-or-more trees (a single scalar still works — it is one
tree). Every immediate subdirectory of every tree is a campaign. For each, reports whether
a `.mneme/` authority is present and which existing wing dirs (those containing a
`mempalace.yaml`) are minable. Discovery is read-only: it observes the live checkout
(FR-014/019) and never writes or drives git. Resolution by name never guesses across trees
(FR-005/006).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hypostasis.models import ConfigEntity, MnemeIdentity

from . import authority as _authority
from . import ownership as _ownership
from .ownership import OwnerState


class DiscoveryError(Exception):
    """No campaigns root configured, a declared tree is missing, or a name can't resolve."""


@dataclass(frozen=True)
class CampaignRef:
    name: str
    path: Path
    has_authority: bool
    wing_dirs: tuple[Path, ...]  # dirs with a mempalace.yaml, for mining
    tree: Path | None = None  # 005 — the declared tree this campaign was found under
    owner_state: OwnerState = OwnerState.UNINTEGRATED  # 005 — membership vs this mneme


def campaigns_roots(entity: ConfigEntity) -> tuple[Path, ...]:
    """The declared campaign trees (one-or-more). Replaces the pre-005 singular root."""
    roots = entity.data_roots.get("campaigns")
    if not roots:
        raise DiscoveryError("hypostasis.yaml has no data_roots.campaigns")
    return tuple(Path(r).expanduser() for r in roots)


def _existing_wing_dirs(campaign_dir: Path) -> tuple[Path, ...]:
    """Dirs under the campaign that contain a `mempalace.yaml` (existing wings)."""
    found = [p.parent for p in campaign_dir.rglob("mempalace.yaml")]
    # Exclude the mneme authority itself (.mneme/mempalace.yaml is NOT a wing).
    found = [d for d in found if d.name != ".mneme"]
    return tuple(sorted(found, key=lambda d: len(d.relative_to(campaign_dir).parts), reverse=True))


def _ref_for(child: Path, tree: Path, identity: MnemeIdentity | None) -> CampaignRef:
    return CampaignRef(
        name=child.name,
        path=child,
        has_authority=_authority.has_authority(child),
        wing_dirs=_existing_wing_dirs(child),
        tree=tree,
        owner_state=_ownership.classify(child, identity),
    )


def discover(entity: ConfigEntity) -> list[CampaignRef]:
    """Every immediate subdirectory of every declared tree is a campaign (FR-003).

    Deterministic ordering by ``(name, tree)`` (FR-010). Read-only (FR-014)."""
    identity = entity.mneme_identity
    refs: list[CampaignRef] = []
    for root in campaigns_roots(entity):
        if not root.is_dir():
            # A declared tree that isn't checked out yet contributes nothing; one absent
            # tree must not wedge the whole fleet (Principle VI). Surfacing it is status's job.
            continue
        for child in sorted(root.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            refs.append(_ref_for(child, root, identity))
    refs.sort(key=lambda r: (r.name, str(r.tree)))
    return refs


def find(entity: ConfigEntity, campaign: str) -> CampaignRef:
    """Resolve a campaign by name across all declared trees, among the campaigns this mneme
    owns (foreign-owned copies are excluded and surfaced separately — FR-005).

    Zero owned matches → not-found error (FR-006); foreign-only copies say so explicitly.
    More than one owned match → ambiguity error naming every tree — never a silent pick."""
    named = [r for r in discover(entity) if r.name == campaign]
    owned = [r for r in named if r.owner_state is not OwnerState.FOREIGN]
    if not owned:
        if named:  # exists, but only as foreign-owned copies
            trees = ", ".join(str(r.tree) for r in named)
            raise DiscoveryError(
                f"campaign '{campaign}' exists only as foreign-owned copies (trees: {trees}) — "
                "not managed by this mneme"
            )
        searched = ", ".join(str(r) for r in campaigns_roots(entity))
        raise DiscoveryError(f"campaign workspace not found: '{campaign}' (searched: {searched})")
    if len(owned) > 1:
        trees = ", ".join(str(m.tree) for m in owned)
        raise DiscoveryError(
            f"campaign '{campaign}' is ambiguous — found under multiple trees: {trees}. "
            "Remove the duplicate or pass an explicit --dir path."
        )
    return owned[0]
