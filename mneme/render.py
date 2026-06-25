"""Render non-authoritative component configs from the authority (jinja2).

Each rendered file is stamped with the SHA-256 of the exact authority *subtree*
it derived from, so `status` can detect drift (a hand-edited copy, or a
`mneme.yaml` changed without `apply`). Rendering is the only write path into a
component's native config — components are never asked to import `mneme`
(low coupling, Principle VII).
"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .models import Component, ConfigEntity, DerivedConfig

TEMPLATES_DIR = Path(__file__).parent / "templates"
STAMP_PREFIX = "# mneme-rendered; source-sha256:"
STAMP_SUFFIX = "do-not-edit"


def component_context(entity: ConfigEntity, comp: Component) -> dict:
    """The exact slice of the authority a component's template may read.

    Hashing this slice (not the whole file) gives *precise* drift detection: the
    stamp changes iff a value this component actually consumes changed.
    """
    return {
        "venv": str(entity.venv),
        "component": {
            "name": comp.name,
            "pin": comp.pin,
            "source": {"kind": comp.source.kind, "locator": comp.source.locator},
            "config_target": str(comp.config_target) if comp.config_target else None,
        },
        "machines": {
            n: {"endpoint": m.endpoint, "default_model": m.default_model}
            for n, m in entity.machines.items()
        },
        "services": {
            n: {"url": s.url, "port": s.port, "managed": s.managed}
            for n, s in entity.services.items()
        },
        "data_roots": {k: str(v) for k, v in entity.data_roots.items()},
    }


def subtree_sha256(context: dict) -> str:
    blob = json.dumps(context, sort_keys=True, separators=(",", ":")).encode()
    return sha256(blob).hexdigest()


def _env(templates_dir: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(templates_dir)),
        undefined=StrictUndefined,  # fail loud on a template/authority mismatch
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_component(
    entity: ConfigEntity, comp: Component, templates_dir: Path = TEMPLATES_DIR
) -> DerivedConfig | None:
    """Render one component's config, or None if it has no template."""
    if not comp.config_template:
        return None
    if not comp.config_target:
        raise ValueError(f"component '{comp.name}': config_template without config_target")
    ctx = component_context(entity, comp)
    digest = subtree_sha256(ctx)
    body = _env(templates_dir).get_template(comp.config_template).render(**ctx)
    return DerivedConfig(
        component=comp.name, target=comp.config_target, source_sha256=digest, content=body
    )


def render_all(
    entity: ConfigEntity, templates_dir: Path = TEMPLATES_DIR
) -> list[DerivedConfig]:
    """Render every component that has a template, in install order (deterministic)."""
    out: list[DerivedConfig] = []
    for name in entity.order.install:
        comp = entity.components[name]
        derived = render_component(entity, comp, templates_dir)
        if derived is not None:
            out.append(derived)
    return out


def stamped_text(derived: DerivedConfig) -> str:
    header = f"{STAMP_PREFIX} {derived.source_sha256}; {STAMP_SUFFIX}\n"
    return header + derived.content


def write_rendered(derived: DerivedConfig) -> Path:
    derived.target.parent.mkdir(parents=True, exist_ok=True)
    derived.target.write_text(stamped_text(derived))
    return derived.target


def render_and_write_all(
    entity: ConfigEntity, templates_dir: Path = TEMPLATES_DIR
) -> list[Path]:
    """Re-render every templated component and write each to its target (the `apply` core).

    Re-rendering is the coherence mechanism (Principle V): the on-disk copy is made
    fresh, so the next consumer reads the current value, never a stale one.
    """
    return [write_rendered(d) for d in render_all(entity, templates_dir)]


def read_stamp(path: Path) -> str | None:
    """Return the stamped source-sha256 from a rendered file's header, or None."""
    try:
        first_line = path.read_text().splitlines()[0]
    except (OSError, IndexError):
        return None
    if STAMP_PREFIX not in first_line:
        return None
    try:
        return first_line.split("source-sha256:")[1].split(";")[0].strip()
    except IndexError:
        return None
