"""Entities for campaign-mempalace management (see data-model.md).

Pure data, no I/O. Authority = the editable source of truth that lives in the
campaign (`CampaignMempalaceConfig`). Derived = regenerated, stamped, never
hand-edited (`RenderedArtifact`). mneme holds no authoritative state of its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

# ---------------------------------------------------------------------------
# Recipe (mneme-owned, versioned)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WingTemplate:
    name: str
    trust: str
    source_hint: str | None = None
    rooms_hint: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScaffoldPattern:
    id: str
    wings: tuple[WingTemplate, ...]


@dataclass(frozen=True)
class MechanicalRules:
    baseline_exclusions: tuple[str, ...]
    mining_order: str = "subscopes_before_root"
    tunnel_rooms: tuple[str, ...] = ()
    hazards: tuple[str, ...] = ()


@dataclass(frozen=True)
class Recipe:
    """The shared best practice — owned by mneme, versioned (FR-007/015)."""

    version: str
    mechanical: MechanicalRules
    scaffold: tuple[ScaffoldPattern, ...] = ()


# ---------------------------------------------------------------------------
# Per-campaign authority (`.mneme/mempalace.yaml`, in the campaign)
# ---------------------------------------------------------------------------

TRUST_LEVELS = ("authoritative", "accelerator", "reference")
DISPOSITION_KINDS = ("deliberate", "pending")


@dataclass(frozen=True)
class Room:
    name: str
    description: str
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class Wing:
    name: str
    source: str  # dir relative to campaign root
    trust: str
    rooms: tuple[Room, ...] = ()


@dataclass(frozen=True)
class Disposition:
    """The recorded *why* for a divergence (FR-027) — human-authored, in-campaign."""

    divergence: str
    kind: str  # "deliberate" | "pending"
    recorded: str  # ISO date
    rationale: str = ""


@dataclass(frozen=True)
class StorePointer:
    """The campaign's declaration of its dedicated store (003 / FR-013) — the single
    source from which all store-naming faces render."""

    alias: str
    path: Path


@dataclass(frozen=True)
class CampaignMempalaceConfig:
    """The single editable authority for one campaign's mempalace (FR-002/016)."""

    campaign: str
    recipe_version: str
    wings: tuple[Wing, ...]
    extra_exclusions: tuple[str, ...] = ()
    dispositions: tuple[Disposition, ...] = ()
    store: StorePointer | None = None  # 003: the dedicated-store pointer (FR-013)
    source_path: Path | None = None

    def disposition_for(self, divergence: str) -> Disposition | None:
        return next((d for d in self.dispositions if d.divergence == divergence), None)


# ---------------------------------------------------------------------------
# Derived render (stamped, do-not-edit)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RenderedArtifact:
    """A regenerated wing `mempalace.yaml` or root `.mempalaceignore`."""

    target: Path  # path RELATIVE to the campaign root
    source_sha256: str
    content: str


# ---------------------------------------------------------------------------
# Observed conformance
# ---------------------------------------------------------------------------


class State(StrEnum):
    BUILT = "built"
    STALE = "stale"
    MISSING_CONFIG = "missing_config"
    INVALID_CONFIG = "invalid_config"
    DIVERGENT_DELIBERATE = "divergent_deliberate"
    DIVERGENT_PENDING = "divergent_pending"
    DIVERGENT_UNDISPOSITIONED = "divergent_undispositioned"
    STALE_RENDER = "stale_render"
    CONFORMANT = "conformant"
    # 005 — campaign↔mneme membership (informational/to-do, not FAIL states)
    OWNED = "owned"
    FOREIGN = "foreign"
    UNINTEGRATED = "unintegrated"
    UNVERIFIABLE = "unverifiable"


# States that count as a genuine FAIL (non-zero exit). A deliberate, recorded
# divergence is NOT a failure; an undispositioned one IS (Principle I).
FAIL_STATES = frozenset(
    {
        State.INVALID_CONFIG,
        State.DIVERGENT_UNDISPOSITIONED,
        State.STALE_RENDER,
    }
)


@dataclass(frozen=True)
class ConformanceRow:
    campaign: str
    dimension: str  # "index" | "render" | "recipe"
    state: State
    observed: str = ""
    expected: str = ""
    disposition: Disposition | None = None
    note: str = ""

    @property
    def ok(self) -> bool:
        return self.state not in FAIL_STATES


@dataclass(frozen=True)
class ConformanceReport:
    rows: tuple[ConformanceRow, ...]

    def for_campaign(self, campaign: str) -> tuple[ConformanceRow, ...]:
        return tuple(r for r in self.rows if r.campaign == campaign)

    def exit_code(self, strict: bool = False) -> int:
        for r in self.rows:
            if not r.ok or (strict and r.state is State.STALE):
                return 1
        return 0


# ---------------------------------------------------------------------------
# Advisory / transient
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TargetConfig:
    """What mneme recommends a campaign adopt (FR-022) — advisory until adopted."""

    campaign: str
    recipe_version: str
    recommended: CampaignMempalaceConfig
    added: tuple[str, ...] = ()
    changed: tuple[str, ...] = ()
    preserved: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()  # would overwrite a deliberate choice (FR-009)


CONTENT_PRESERVING_OPS = ("move", "split", "rename", "reindex", "write_authority")


@dataclass(frozen=True)
class MigrationStep:
    op: str  # one of CONTENT_PRESERVING_OPS — NO "rewrite_content"
    args: dict = field(default_factory=dict)


@dataclass(frozen=True)
class MigrationPlan:
    campaign: str
    steps: tuple[MigrationStep, ...]
    approved_by_human: bool = False


@dataclass(frozen=True)
class WorkingCopy:
    """mneme's private clone of the campaigns repo (holds no authority)."""

    path: Path
    branch: str
    remote: str = ""


# ---------------------------------------------------------------------------
# 003 — store provisioning, health, backup, bring-up
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DedicatedStore:
    """The campaign's turbovec store on disk (derived/rebuildable; never authority)."""

    path: Path
    present: bool
    bindings_files: tuple[Path, ...] = ()  # turbovec/*/store.sqlite3 + knowledge_graph.sqlite3
    rebuildable_files: tuple[Path, ...] = ()  # index.tvim (regenerated, no re-embed)
    legacy_files: tuple[Path, ...] = ()  # chroma.sqlite3 + segments (dead)


class StoreState(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    MISSING = "missing"


@dataclass(frozen=True)
class StoreHealth:
    """Observed store health for the `mneme up` gate (D5) + status (IX)."""

    present: bool
    state: StoreState
    note: str = ""

    @property
    def ok(self) -> bool:
        return self.state is StoreState.HEALTHY


@dataclass(frozen=True)
class BindingsBackup:
    """A derived/disposable snapshot of the bindings (FR-011) — never an authority."""

    campaign: str
    location: Path
    taken: str = ""  # ISO date, stamped after the run
    contents: tuple[Path, ...] = ()


@dataclass(frozen=True)
class BringUpStep:
    name: str  # configure | render_faces | provision | first_mine | backup
    state: str  # ok | skipped | failed
    observed: str = ""
    note: str = ""


@dataclass(frozen=True)
class BringUpReport:
    campaign: str
    steps: tuple[BringUpStep, ...]
    owed: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        return all(s.state != "failed" for s in self.steps)

    def exit_code(self) -> int:
        return 0 if self.ready else 1
