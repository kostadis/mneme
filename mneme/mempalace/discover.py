"""Discover the campaigns mneme manages across one or more trees (005, FR-001/003).

``data_roots.campaigns`` is one-or-more trees (a single scalar still works — it is one
tree). Every immediate subdirectory of every tree is a campaign. For each, reports whether
a `.mneme/` authority is present and which existing wing dirs (those containing a
`mempalace.yaml`) are minable. Discovery is read-only: it observes the live checkout
(FR-014/019) and never writes or drives git. Resolution by name never guesses across trees
(FR-005/006).
"""

from __future__ import annotations

import os
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
    """Dirs under the campaign that contain a `mempalace.yaml` (existing wings).

    Bounded to the campaign: `os.walk(followlinks=False)` rather than `rglob`, which follows
    symlinks and would escape into the host filesystem (GH #35)."""
    found = [
        Path(root)
        for root, _dirs, files in os.walk(campaign_dir, followlinks=False)
        if "mempalace.yaml" in files
    ]
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
            # A symlinked entry is not a campaign. `is_dir()` follows symlinks, so without
            # this guard an unrelated link (e.g. `~/campaigns/mnt -> /mnt/`) is treated as a
            # campaign and the wing walk escapes into the host filesystem (GH #35).
            if child.is_symlink() or not child.is_dir() or child.name.startswith("."):
                continue
            refs.append(_ref_for(child, root, identity))
    refs.sort(key=lambda r: (r.name, str(r.tree)))
    return refs


def _this_mneme(entity: ConfigEntity) -> str:
    ident = entity.mneme_identity
    return ident.id if ident and ident.id else "not established"


def foreign_refusal(entity: ConfigEntity, ref: CampaignRef) -> str:
    """The one ownership refusal message, shared by every route (006, FR-009).

    Names the campaign's declared owner, this mneme's identity (or its absence), and the
    remedy. The pre-006 message named none of those, so the only way forward was reading
    the source."""
    owner = _ownership.read_owner(ref.path)
    owner_id = owner.mneme_id if owner else "?"
    mine = _this_mneme(entity)
    return (
        f"campaign '{ref.name}' is owned by {owner_id}; this mneme is {mine}. "
        f"If this host should join that fleet:  mneme identity adopt {owner_id}"
    )


def alias_conflicts(entity: ConfigEntity) -> dict[str, list[str]]:
    """Store aliases claimed by more than one campaign (006, FR-016/016a).

    Since the store location derives from the alias, a duplicate alias means two campaigns
    resolve to ONE store and would commingle their content. Uniqueness is a fleet-level
    invariant, so even a single-campaign command consults discovery to enforce it.
    Tolerant: a campaign whose authority won't load contributes nothing (Principle VI)."""
    by_alias: dict[str, list[str]] = {}
    for ref in discover(entity):
        if not ref.has_authority:
            continue
        try:
            cfg = _authority.load(ref.path)
        except _authority.AuthorityError:
            continue
        if cfg.store is not None:
            by_alias.setdefault(cfg.store.alias, []).append(ref.name)
    return {a: sorted(c) for a, c in sorted(by_alias.items()) if len(c) > 1}


def find(entity: ConfigEntity, campaign: str) -> CampaignRef:
    """Resolve a campaign by name across all declared trees, among the campaigns this mneme
    owns (foreign-owned copies are excluded and surfaced separately — FR-005).

    Zero owned matches → not-found error (FR-006); foreign-only copies say so explicitly.
    More than one owned match → ambiguity error naming every tree — never a silent pick.

    Ownership is used here only to *disambiguate* — a foreign copy must not make a name
    ambiguous. Enforcement lives in ``resolve``, so it applies to ``--dir`` too (FR-018)."""
    named = [r for r in discover(entity) if r.name == campaign]
    owned = [r for r in named if r.owner_state is not OwnerState.FOREIGN]
    if not owned:
        if named:  # exists, but only as foreign-owned copies
            raise DiscoveryError(foreign_refusal(entity, named[0]))
        searched = ", ".join(str(r) for r in campaigns_roots(entity))
        raise DiscoveryError(f"campaign workspace not found: '{campaign}' (searched: {searched})")
    if len(owned) > 1:
        trees = ", ".join(str(m.tree) for m in owned)
        raise DiscoveryError(
            f"campaign '{campaign}' is ambiguous — found under multiple trees: {trees}. "
            "Remove the duplicate or pass an explicit --dir path."
        )
    return owned[0]


def ref_for_dir(entity: ConfigEntity, campaign_dir) -> CampaignRef:
    """Build a CampaignRef for an explicit campaign workspace path (the ``--dir`` override).

    Bypasses tree discovery and the *ambiguity* guard — the caller names the exact workspace
    (GH #27). It does NOT bypass ownership: that gate lives in ``resolve`` (FR-018)."""
    p = Path(campaign_dir).expanduser()
    if not p.is_dir():
        raise DiscoveryError(f"campaign workspace not found: {p}")
    return _ref_for(p, p.parent, entity.mneme_identity)


def resolve(entity: ConfigEntity, campaign: str | None, campaign_dir=None) -> CampaignRef:
    """Resolve one campaign to a ref — an explicit ``--dir`` path wins over the name lookup.

    ``--dir`` lets `mneme mp` act on a specific workspace when the name is ambiguous across
    declared trees (GH #27). It is an **ambiguity** escape hatch and nothing more: ownership
    (FR-018) and store-alias uniqueness (FR-016a) are enforced here, so both routes are
    treated identically. Before 006, `--dir` skipped the ownership gate as a side effect of
    sharing `find()`, which made it an undocumented take-over path."""
    ref = ref_for_dir(entity, campaign_dir) if campaign_dir else find(entity, campaign)
    if ref.owner_state is OwnerState.FOREIGN:
        raise DiscoveryError(foreign_refusal(entity, ref))
    conflicts = alias_conflicts(entity)
    for alias, camps in conflicts.items():
        if ref.name in camps:
            raise DiscoveryError(
                f"store alias '{alias}' is claimed by {len(camps)} campaigns "
                f"({', '.join(camps)}) — they would share one store. Give each campaign its "
                "own `store.alias` in .mneme/mempalace.yaml before continuing."
            )
    return ref
