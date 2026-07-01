"""Config-entity dataclasses (see specs/.../data-model.md).

Pure data, no I/O. The ConfigEntity is the in-memory form of the single authority
(`hypostasis.yaml`). DerivedConfig is a *non-authoritative* rendered artifact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Machine:
    endpoint: str
    default_model: str | None = None


@dataclass(frozen=True)
class Health:
    type: str = "tcp"  # "tcp" | "http"
    path: str | None = None


@dataclass(frozen=True)
class Service:
    name: str
    url: str
    port: int | None = None
    managed: bool = False
    health: Health | None = None
    start: str | None = None
    stop: str | None = None


@dataclass(frozen=True)
class Source:
    kind: str  # "pypi" | "path" | "git"
    locator: str  # package name, filesystem path, or git URL


@dataclass(frozen=True)
class Component:
    name: str
    source: Source
    pin: str
    config_template: str | None = None
    config_target: Path | None = None


@dataclass(frozen=True)
class Order:
    install: tuple[str, ...]
    startup: tuple[str, ...]


@dataclass(frozen=True)
class MnemeIdentity:
    """The logical fleet identity (005). Generated, host-independent; the owner stamped
    into a campaign's `.mneme/owner.yaml`. ``id`` is authoritative for ownership; ``label``
    is an optional human-readable name (informational only)."""

    id: str
    label: str | None = None


def _as_root_tuple(value) -> tuple[Path, ...]:
    """Normalize a data_roots value to a tuple of Paths (005, FR-001/002).

    A scalar (str/Path) becomes a 1-tuple — so the pre-005 scalar shape and direct
    construction keep working — and a list/tuple becomes an N-tuple.
    """
    if isinstance(value, (str, Path)):
        return (Path(value),)
    return tuple(Path(v) for v in value)


@dataclass(frozen=True)
class ConfigEntity:
    """The single authoritative config/wiring entity (`hypostasis.yaml`)."""

    venv: Path
    machines: dict[str, Machine]
    services: dict[str, Service]
    components: dict[str, Component]
    order: Order
    # Each key maps to one-or-more roots (005). `campaigns` may name several trees; other
    # keys are single-valued — read them via `hypostasis.config.single_root`.
    data_roots: dict[str, tuple[Path, ...]] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)  # exported to managed services on `up`
    mneme_identity: MnemeIdentity | None = None  # 005 — minted lazily if absent
    source_path: Path | None = None

    def __post_init__(self) -> None:
        # Normalize every data_roots value to a tuple[Path, ...] so direct construction
        # (tests, callers) may still pass a bare Path/str.
        norm = {k: _as_root_tuple(v) for k, v in self.data_roots.items()}
        object.__setattr__(self, "data_roots", norm)


@dataclass(frozen=True)
class DerivedConfig:
    """A regenerated, non-authoritative component config (data-model.md).

    Carries the SHA-256 of the authority subtree it was rendered from, so drift
    (a stale or hand-edited copy) is detectable (Principle V / Principle I).
    """

    component: str
    target: Path
    source_sha256: str
    content: str
