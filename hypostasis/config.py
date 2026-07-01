"""Load and validate the single authority (`hypostasis.yaml`).

Loading is tolerant (it parses what it can so that validation can report *all*
problems at once); validation enforces the invariants from the schema contract
(contracts/hypostasis-yaml.schema.md). Any violation raises ConfigError, which the
CLI maps to exit code 2 — before any side effect.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import yaml

from .models import (
    Component,
    ConfigEntity,
    Health,
    Machine,
    MnemeIdentity,
    Order,
    Service,
    Source,
)

# Top-level keys that would establish a SECOND writable authority (Principle V).
FORBIDDEN_TOP_LEVEL = (
    "lockfile",
    "lock",
    "installed",
    "installed_versions",
    "state_db",
    "writeback",
    "write_back",
)


class ConfigError(Exception):
    """Schema / integrity / cycle / authority violation. CLI maps to exit 2."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("invalid hypostasis.yaml:\n  - " + "\n  - ".join(problems))


def _expand(value: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(str(value))))


def _normalize_roots(value) -> tuple[Path, ...]:
    """A data_roots value is one-or-more paths (005). Scalar → 1-tuple (backward
    compatible), list → N-tuple; every element is ~/env expanded."""
    items = value if isinstance(value, list) else [value]
    return tuple(_expand(v) for v in items)


def _is_within(child: Path, parent: Path) -> bool:
    """True if ``child`` is ``parent`` or nested under it (path-prefix, 005)."""
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def single_root(entity, key: str) -> Path | None:
    """Return the sole root for a single-valued data_roots key (e.g. ``backups``).

    Returns None if the key is absent. Raises ConfigError if the key was declared with
    more than one path — those keys are not multi-root (only ``campaigns`` is, 005)."""
    roots = entity.data_roots.get(key)
    if not roots:
        return None
    if len(roots) > 1:
        raise ConfigError([f"data_roots.{key}: expects a single path, got {len(roots)}"])
    return roots[0]


def default_config_path() -> Path:
    """XDG location of the environment authority.

    ``$XDG_CONFIG_HOME/hypostasis/hypostasis.yaml`` (default
    ``~/.config/hypostasis/hypostasis.yaml``). The config lives in the user's config
    dir, never in the repo — the repo ships only ``hypostasis.example.yaml``.
    """
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "hypostasis" / "hypostasis.yaml"


def _is_range_or_editable(pin: str) -> bool:
    """A pin must be an *exact* version or git ref — no ranges, no editable installs."""
    pin = pin.strip()
    if not pin:
        return True
    if pin.startswith(("-e", "--editable")):
        return True
    # any comparison/wildcard operator or whitespace ⇒ not an exact pin
    return any(tok in pin for tok in ("=", ">", "<", "*", "~", "!", ",", " "))


def _parse_source(raw_source, comp_name: str, problems: list[str]) -> Source:
    if not isinstance(raw_source, dict):
        problems.append(f"component '{comp_name}': source must be a mapping")
        return Source(kind="?", locator="?")
    for kind in ("pypi", "path", "git"):
        if kind in raw_source:
            return Source(kind=kind, locator=str(raw_source[kind]))
    problems.append(
        f"component '{comp_name}': source must specify one of pypi / path / git"
    )
    return Source(kind="?", locator="?")


def _parse(raw: dict, path: Path, problems: list[str]) -> ConfigEntity:
    venv = _expand(raw["venv"]) if raw.get("venv") else Path()
    if not raw.get("venv"):
        problems.append("missing required field: venv")

    machines: dict[str, Machine] = {}
    for name, m in (raw.get("machines") or {}).items():
        m = m or {}
        machines[name] = Machine(
            endpoint=m.get("endpoint", ""), default_model=m.get("default_model")
        )

    services: dict[str, Service] = {}
    for name, s in (raw.get("services") or {}).items():
        s = s or {}
        h = s.get("health")
        health = (
            Health(type=(h or {}).get("type", "tcp"), path=(h or {}).get("path"))
            if h
            else None
        )
        services[name] = Service(
            name=name,
            url=s.get("url", ""),
            port=s.get("port"),
            managed=bool(s.get("managed", False)),
            health=health,
            start=s.get("start"),
            stop=s.get("stop"),
        )

    components: dict[str, Component] = {}
    for name, c in (raw.get("components") or {}).items():
        c = c or {}
        components[name] = Component(
            name=name,
            source=_parse_source(c.get("source"), name, problems),
            pin=str(c.get("pin", "")),
            config_template=c.get("config_template"),
            config_target=_expand(c["config_target"]) if c.get("config_target") else None,
        )

    o = raw.get("order") or {}
    order = Order(
        install=tuple(o.get("install") or ()),
        startup=tuple(o.get("startup") or ()),
    )

    data_roots = {k: _normalize_roots(v) for k, v in (raw.get("data_roots") or {}).items()}

    # 005 — the logical fleet identity (optional; minted lazily by ensure_mneme_identity).
    mneme_block = raw.get("mneme") or {}
    mneme_identity = (
        MnemeIdentity(id=str(mneme_block.get("id") or ""), label=mneme_block.get("label"))
        if mneme_block
        else None
    )

    # Process environment exported to managed services on `up` (env-wiring, e.g.
    # MEMPALACE_BACKEND). Values must be scalars — they become env var strings.
    env: dict[str, str] = {}
    for k, v in (raw.get("env") or {}).items():
        if isinstance(v, (str, int, float, bool)):
            env[str(k)] = str(v)
        else:
            problems.append(
                f"env.{k}: value must be a scalar (string/number/bool), got {type(v).__name__}"
            )

    return ConfigEntity(
        venv=venv,
        machines=machines,
        services=services,
        components=components,
        order=order,
        data_roots=data_roots,
        env=env,
        mneme_identity=mneme_identity,
        source_path=path,
    )


def _dup_problems(label: str, names: tuple[str, ...]) -> list[str]:
    seen, dups = set(), set()
    for n in names:
        (dups if n in seen else seen).add(n)
    return [f"{label}: '{n}' appears more than once (order must be a well-defined sequence)"
            for n in sorted(dups)]


def validate(entity: ConfigEntity, raw: dict) -> list[str]:
    """Return a list of invariant violations (empty ⇒ valid). See schema contract."""
    p: list[str] = []

    # Single authority (Principle V): no field may point at a second writable store.
    for key in FORBIDDEN_TOP_LEVEL:
        if key in raw:
            p.append(
                f"forbidden field '{key}': would create a second authority (Principle V)"
            )

    # Required presence.
    if not entity.machines:
        p.append("machines: at least one machine is required")
    elif "dgx" not in entity.machines:
        p.append("machines: must include 'dgx'")
    if not entity.components:
        p.append("components: at least one is required")
    if not entity.order.install:
        p.append("order.install: required")
    if not entity.order.startup:
        p.append("order.startup: required")

    for name, c in entity.components.items():
        # Invariant 1 — exact pins.
        if not c.pin:
            p.append(f"component '{name}': missing pin")
        elif _is_range_or_editable(c.pin):
            p.append(
                f"component '{name}': pin '{c.pin}' is a range/editable — "
                "an exact version or git ref is required (invariant 1)"
            )
        if c.source.kind not in ("pypi", "path", "git"):
            p.append(f"component '{name}': unresolved source")
        # Invariant 5 — template requires a target.
        if c.config_template and not c.config_target:
            p.append(
                f"component '{name}': config_template set but config_target missing "
                "(invariant 5)"
            )

    # Invariant 2 — referential integrity.
    for n in entity.order.install:
        if n not in entity.components:
            p.append(f"order.install: '{n}' is not a declared component (invariant 2)")
    for n in entity.order.startup:
        if n not in entity.services:
            p.append(f"order.startup: '{n}' is not a declared service (invariant 2)")

    # Invariant 3 — acyclicity. order.* are explicit total orders, so the only way to
    # make them ill-defined is to list a name twice (a contradictory ordering).
    p += _dup_problems("order.install", entity.order.install)
    p += _dup_problems("order.startup", entity.order.startup)

    # Invariant 4 — managed services declare start/stop.
    for name, s in entity.services.items():
        if s.managed and (not s.start or not s.stop):
            p.append(
                f"service '{name}': managed=true requires both 'start' and 'stop' "
                "(invariant 4)"
            )

    # Path sanity — absolute after ~/env expansion.
    if entity.venv and not entity.venv.is_absolute():
        p.append(f"venv '{entity.venv}' must resolve to an absolute path")
    for name, c in entity.components.items():
        if c.config_target and not c.config_target.is_absolute():
            p.append(f"component '{name}': config_target must be an absolute path")
    for k, roots in entity.data_roots.items():
        for r in roots:
            if not r.is_absolute():
                p.append(f"data_roots.{k}: '{r}' must resolve to an absolute path")

    # 005 — the campaigns trees must not overlap/nest, or a campaign is discovered twice.
    camp = entity.data_roots.get("campaigns") or ()
    for i, a in enumerate(camp):
        for b in camp[i + 1 :]:
            if a == b or _is_within(a, b) or _is_within(b, a):
                p.append(
                    f"data_roots.campaigns: trees '{a}' and '{b}' overlap or nest "
                    "(declared trees must be disjoint)"
                )

    # 005 — if a mneme: block is declared, its id must be non-empty (FR-012).
    if "mneme" in raw and not (raw.get("mneme") or {}).get("id"):
        p.append("mneme.id: required when a mneme: block is present")

    return p


def load(path: str | Path) -> ConfigEntity:
    """Parse and validate `hypostasis.yaml`. Raises ConfigError on any violation."""
    path = Path(path)
    text = path.read_text()  # FileNotFoundError handled by the CLI
    try:
        raw = yaml.safe_load(text) or {}
    except yaml.YAMLError as e:
        raise ConfigError([f"YAML parse error: {e}"]) from e
    if not isinstance(raw, dict):
        raise ConfigError(["top level of hypostasis.yaml must be a mapping"])

    problems: list[str] = []
    entity = _parse(raw, path, problems)
    problems += validate(entity, raw)
    if problems:
        raise ConfigError(problems)
    return entity


def ensure_mneme_identity(config_path: str | Path, *, label: str | None = None) -> MnemeIdentity:
    """Return the mneme identity, minting one if absent (005, FR-012).

    A fresh ``uuid4`` is generated and the ``mneme:`` block is **appended** to the file
    (existing content/comments preserved — never a full rewrite), honoring "the human owns
    hypostasis.yaml". Idempotent: once an id exists it is returned unchanged."""
    config_path = Path(config_path)
    entity = load(config_path)
    if entity.mneme_identity and entity.mneme_identity.id:
        return entity.mneme_identity
    new = MnemeIdentity(id=str(uuid.uuid4()), label=label)
    block = f"\nmneme:\n  id: {new.id}\n"
    if new.label:
        block += f"  label: {new.label}\n"
    text = config_path.read_text()
    config_path.write_text(text.rstrip("\n") + "\n" + block)
    return new
