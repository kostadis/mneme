"""Campaign ownership — the `.mneme/owner.yaml` membership record (005, FR-013/015/016).

A campaign self-declares which mneme owns it. The record is **separate** from the
`.mneme/mempalace.yaml` indexing authority, so it can exist at the *integrated* stage,
before bring-up. It is authoritative for ownership only; its sole writers are
`mneme integrate` and `mneme up`. It is host-independent: no machine coordinate appears
in it, so the campaign can be brought up by any runtime carrying the owning identity
(FR-019). See contracts/owner-yaml.schema.md.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import yaml

from hypostasis.models import MnemeIdentity

OWNER_RELPATH = Path(".mneme") / "owner.yaml"
SCHEMA_VERSION = "1.0.0"


class OwnerState(str, Enum):
    UNINTEGRATED = "unintegrated"  # no owner.yaml
    OWNED = "owned"  # owner id == this runtime's id
    FOREIGN = "foreign"  # owner id != this runtime's id
    UNVERIFIABLE = "unverifiable"  # this runtime has no identity yet — can't classify


class OwnershipError(Exception):
    """A claim could not proceed (e.g. the campaign is foreign-owned)."""


@dataclass(frozen=True)
class Owner:
    schema_version: str
    mneme_id: str  # the ONLY field used for classification
    label: str | None = None  # informational snapshot
    integrated_at: str | None = None  # informational


def owner_path(campaign_dir: Path) -> Path:
    return Path(campaign_dir) / OWNER_RELPATH


def read_owner(campaign_dir: Path) -> Owner | None:
    p = owner_path(campaign_dir)
    if not p.is_file():
        return None
    raw = yaml.safe_load(p.read_text()) or {}
    m = raw.get("mneme") or {}
    return Owner(
        schema_version=str(raw.get("schema_version", "")),
        mneme_id=str(m.get("id", "")),
        label=m.get("label"),
        integrated_at=raw.get("integrated_at"),
    )


def classify(campaign_dir: Path, identity: MnemeIdentity | None) -> OwnerState:
    owner = read_owner(campaign_dir)
    if owner is None:
        return OwnerState.UNINTEGRATED
    if identity is None or not identity.id:
        return OwnerState.UNVERIFIABLE
    return OwnerState.OWNED if owner.mneme_id == identity.id else OwnerState.FOREIGN


def write_owner(campaign_dir: Path, identity: MnemeIdentity, *, now: _dt.datetime | None = None) -> Owner:
    """Write `.mneme/owner.yaml` (and `.mneme/` if missing) — and nothing else (SC-007)."""
    ts = (now or _dt.datetime.now(_dt.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    mneme: dict = {"id": identity.id}
    if identity.label:
        mneme["label"] = identity.label
    data = {"schema_version": SCHEMA_VERSION, "mneme": mneme, "integrated_at": ts}
    p = owner_path(campaign_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(data, sort_keys=False))
    return Owner(SCHEMA_VERSION, identity.id, identity.label, ts)


def integrate_campaign(campaign_dir: Path, identity: MnemeIdentity) -> Owner:
    """Claim a campaign for ``identity``: write owner.yaml if unintegrated, no-op if already
    owned (idempotent), refuse if foreign-owned (FR-015/016)."""
    state = classify(campaign_dir, identity)
    if state is OwnerState.FOREIGN:
        owner = read_owner(campaign_dir)
        raise OwnershipError(
            f"{campaign_dir} is owned by a different mneme "
            f"({owner.mneme_id if owner else '?'}) — refusing to manage or re-stamp"
        )
    if state is OwnerState.OWNED:
        return read_owner(campaign_dir)  # idempotent
    return write_owner(campaign_dir, identity)
