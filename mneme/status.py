"""Honest status — observed vs declared (Principle I: Silicon Truth).

`status` never echoes `mneme.yaml` as if it were reality. It reads the silicon:
- component drift: the source repo's HEAD vs the declared `pin` (catches the
  editable-install drift this whole project exists to kill);
- service reachability: a live probe (never "should be up");
- render drift: a rendered config's stamped source-hash vs the current authority.

Exit 0 only if EVERY check passes; 1 if any fails.

Honest limitation: for path-installed components we compare the *source tree*'s
HEAD to the pin, not the installed bytes (PEP 610 `direct_url` for a path install
records no commit). A fuller "installed == pin" check is a future enhancement.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from importlib import metadata as _md
from pathlib import Path

from . import probe as _probe
from . import render as _render
from .models import Component, ConfigEntity, Service

Runner = Callable[[list[str]], "subprocess.CompletedProcess[str]"]
Prober = Callable[[Service], bool]


@dataclass(frozen=True)
class Row:
    name: str
    kind: str  # "component" | "render" | "service"
    observed: str
    expected: str
    ok: bool
    note: str = ""


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True)


def _git_head(path: Path, runner: Runner) -> str | None:
    result = runner(["git", "-C", str(path), "rev-parse", "HEAD"])
    return result.stdout.strip() if result.returncode == 0 else None


def _installed_version(dist: str) -> str | None:
    try:
        return _md.version(dist)
    except _md.PackageNotFoundError:
        return None


def component_row(comp: Component, runner: Runner = _run) -> Row:
    """Source-HEAD-vs-pin drift for a component (the silicon truth of the pin)."""
    expected = comp.pin
    short = expected[:12]

    if comp.source.kind == "pypi":
        version = _installed_version(comp.source.locator)
        return Row(
            comp.name, "component", version or "(absent)", expected,
            version == expected, "" if version else "not installed",
        )

    # path / git source — pin is a git ref; compare the source tree's HEAD.
    src = Path(comp.source.locator).expanduser()
    head = _git_head(src, runner)
    version = _installed_version(comp.name)
    inst = f"installed {version}" if version else "not a pip dist (source-run)"
    if head is None:
        return Row(comp.name, "component", "?", short, False, f"source not a git repo: {src}")
    ok = head == expected
    note = inst if ok else f"{inst}; source HEAD drifted from pin"
    return Row(comp.name, "component", head[:12], short, ok, note)


def render_row(entity: ConfigEntity, comp: Component) -> Row:
    """Drift between a rendered config's stamped hash and the current authority."""
    target = comp.config_target
    if target is None:
        return Row(comp.name, "render", "—", "—", True, "no render target")
    if not target.exists():
        return Row(comp.name, "render", "(not rendered)", "stamped", False,
                   "config_target missing — run `mneme apply`")
    stamped = _render.read_stamp(target)
    current = _render.subtree_sha256(_render.component_context(entity, comp))
    ok = stamped == current
    return Row(comp.name, "render", (stamped or "?")[:12], current[:12], ok,
               "" if ok else "stale render — run `mneme apply`")


def service_row(name: str, service: Service, prober: Prober = _probe.reachable) -> Row:
    up = prober(service)
    note = "managed" if service.managed else "external"
    return Row(name, "service", "reachable" if up else "UNREACHABLE", "reachable", up, note)


def status_report(
    entity: ConfigEntity, runner: Runner = _run, prober: Prober = _probe.reachable
) -> tuple[list[Row], int]:
    """All rows + exit code (0 iff every row PASS)."""
    rows: list[Row] = []
    for name in entity.order.install:
        rows.append(component_row(entity.components[name], runner))
    for name in entity.order.install:
        comp = entity.components[name]
        if comp.config_template:
            rows.append(render_row(entity, comp))
    for name in entity.order.startup:
        service = entity.services.get(name)
        if service is not None:
            rows.append(service_row(name, service, prober))
    code = 0 if all(r.ok for r in rows) else 1
    return rows, code
