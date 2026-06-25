"""Install components at exact pins (non-editable) in declared order.

Fail loud (Principle I / FR-006): the first component that cannot be installed at
its exact pin raises InstallError naming it; the run never reports success on a
partial result. The command runner is injectable so the orchestration can be
tested without a real venv or network.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from .models import Component, ConfigEntity

Runner = Callable[[list[str]], "subprocess.CompletedProcess[str]"]


class InstallError(Exception):
    def __init__(self, component: str, detail: str):
        self.component = component
        self.detail = detail
        super().__init__(f"install failed for '{component}': {detail}")


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True)


def ensure_venv(venv: Path, runner: Runner = _run) -> Path:
    """Return the venv's python, creating the venv if absent."""
    py = venv / "bin" / "python"
    if py.exists():
        return py
    venv.parent.mkdir(parents=True, exist_ok=True)
    result = runner([sys.executable, "-m", "venv", str(venv)])
    if result.returncode != 0:
        raise InstallError("<venv>", result.stderr.strip() or "venv creation failed")
    return py


def pip_target(comp: Component) -> str:
    """Translate a component + exact pin into a non-editable pip target."""
    src = comp.source
    if src.kind == "pypi":
        return f"{src.locator}=={comp.pin}"
    if src.kind == "git":
        url = src.locator if src.locator.startswith("git+") else f"git+{src.locator}"
        return f"{url}@{comp.pin}"
    if src.kind == "path":
        return str(Path(src.locator).expanduser())
    raise InstallError(comp.name, f"unknown source kind {src.kind!r}")


def _verify_path_pin(comp: Component, runner: Runner) -> None:
    """For a local path source, refuse to install unless the tree is AT the pin.

    We verify, we do not check out — mutating the user's working tree would be a
    side effect on a repo we do not own (Principle IV / honesty).
    """
    repo = Path(comp.source.locator).expanduser()
    head = runner(["git", "-C", str(repo), "rev-parse", "HEAD"])
    if head.returncode != 0:
        raise InstallError(comp.name, f"not a git repo: {repo}")
    observed = head.stdout.strip()
    want = runner(["git", "-C", str(repo), "rev-parse", f"{comp.pin}^{{commit}}"])
    if want.returncode == 0 and want.stdout.strip() != observed:
        raise InstallError(
            comp.name,
            f"working tree at {observed[:12]} != pinned {comp.pin} — "
            "checkout the pin or update mneme.yaml",
        )


def install_component(py: Path, comp: Component, runner: Runner = _run) -> None:
    if comp.source.kind == "path":
        _verify_path_pin(comp, runner)
    target = pip_target(comp)
    result = runner([str(py), "-m", "pip", "install", "--upgrade", target])
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "pip install failed").strip()
        raise InstallError(comp.name, detail[-400:])


def install_all(entity: ConfigEntity, runner: Runner = _run) -> list[str]:
    """Install every component in `order.install`. Returns the installed names."""
    py = ensure_venv(entity.venv, runner)
    installed: list[str] = []
    for name in entity.order.install:
        install_component(py, entity.components[name], runner)
        installed.append(name)
    return installed
