"""Config-entity dataclasses (see specs/.../data-model.md).

Pure data, no I/O. The ConfigEntity is the in-memory form of the single authority
(`mneme.yaml`). DerivedConfig is a *non-authoritative* rendered artifact.
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
class ConfigEntity:
    """The single authoritative config/wiring entity (`mneme.yaml`)."""

    venv: Path
    machines: dict[str, Machine]
    services: dict[str, Service]
    components: dict[str, Component]
    order: Order
    data_roots: dict[str, Path] = field(default_factory=dict)
    source_path: Path | None = None


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
