"""T010 — install orchestration: pins honored, order respected, fail-loud (FR-006).

The command runner is injected so the orchestration (correct pip targets, declared
order, fail-loud naming) is tested deterministically without a network. A separate
slow test exercises real venv creation. The full real install→render loop is the
container acid test (T034), not duplicated here.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess

import pytest

from hypostasis import install as inst
from hypostasis.models import Component, ConfigEntity, Machine, Order, Source


class FakeRunner:
    def __init__(self, fail_substr: str | None = None):
        self.calls: list[list[str]] = []
        self.fail_substr = fail_substr

    def __call__(self, cmd):
        self.calls.append(list(cmd))
        rc = 1 if self.fail_substr and any(self.fail_substr in p for p in cmd) else 0
        return subprocess.CompletedProcess(
            cmd, rc, stdout="", stderr=f"boom: {self.fail_substr}" if rc else ""
        )

    def pip_targets(self) -> list[str]:
        return [c[-1] for c in self.calls if "install" in c]


def make_entity(tmp_path, installer="pip"):
    comps = {
        "a": Component("a", Source("pypi", "pkgA"), "1.0"),
        "b": Component("b", Source("pypi", "pkgB"), "2.0"),
    }
    return ConfigEntity(
        venv=tmp_path / "venv",
        machines={"dgx": Machine("http://dgx")},
        services={},
        components=comps,
        order=Order(install=("a", "b"), startup=()),
        installer=installer,
    )


def test_install_all_honors_pins_and_order(tmp_path):
    runner = FakeRunner()
    installed = inst.install_all(make_entity(tmp_path), runner)
    assert installed == ["a", "b"]  # declared order
    assert runner.pip_targets() == ["pkgA==1.0", "pkgB==2.0"]  # exact pins


def test_install_fails_loud_and_names_component(tmp_path):
    runner = FakeRunner(fail_substr="pkgB")
    with pytest.raises(inst.InstallError) as ei:
        inst.install_all(make_entity(tmp_path), runner)
    assert ei.value.component == "b"  # FR-006: names the offending unit
    # 'a' was attempted, 'b' failed — never reports success on a partial result
    assert "pkgA==1.0" in runner.pip_targets()


def test_install_all_uv_shells_out_to_uv(tmp_path, monkeypatch):
    # uv is on PATH (preflight passes) — assert the uv command forms are used.
    monkeypatch.setattr(inst.shutil, "which", lambda name: "/usr/bin/uv")
    runner = FakeRunner()
    installed = inst.install_all(make_entity(tmp_path, installer="uv"), runner)
    assert installed == ["a", "b"]
    # venv is created with `uv venv`, not stdlib venv.
    assert ["uv", "venv", str(tmp_path / "venv")] in runner.calls
    # each install is `uv pip install --python <py> --upgrade <target>` (pin LAST).
    assert runner.calls[1][:3] == ["uv", "pip", "install"]
    assert "--python" in runner.calls[1]
    assert runner.pip_targets() == ["pkgA==1.0", "pkgB==2.0"]  # pin-last invariant preserved


def test_install_all_uv_missing_binary_fails_loud(tmp_path, monkeypatch):
    # installer=uv but uv absent → fail loud, named, before any side effect.
    monkeypatch.setattr(inst.shutil, "which", lambda name: None)
    runner = FakeRunner()
    with pytest.raises(inst.InstallError) as ei:
        inst.install_all(make_entity(tmp_path, installer="uv"), runner)
    assert ei.value.component == "<uv>"
    assert runner.calls == []  # nothing ran — no venv, no install


def test_pip_target_translations():
    pypi = Component("p", Source("pypi", "pkg"), "3.3.5")
    git = Component("g", Source("git", "https://x/y.git"), "abc123")
    assert inst.pip_target(pypi) == "pkg==3.3.5"
    assert inst.pip_target(git) == "git+https://x/y.git@abc123"


def test_path_pin_mismatch_fails_loud(tmp_path):
    """A local path source whose HEAD != pin must refuse to install (honesty)."""
    comp = Component("c", Source("path", str(tmp_path / "repo")), "1111111")

    def runner(cmd):
        # git rev-parse HEAD -> some sha; rev-parse pin^{commit} -> a DIFFERENT sha
        if "rev-parse" in cmd and "HEAD" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="2222222\n", stderr="")
        if "rev-parse" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="3333333\n", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    with pytest.raises(inst.InstallError) as ei:
        inst.install_component(tmp_path / "venv" / "bin" / "python", comp, runner)
    assert ei.value.component == "c"
    assert "!=" in ei.value.detail


def _assert_real_venv_python_runs(venv, py):
    assert py.exists(), "venv python should exist after creation"
    out = subprocess.run(
        [str(py), "-c", "import sys; print(sys.executable)"],
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0
    assert str(venv) in out.stdout


@pytest.mark.slow
@pytest.mark.skipif(
    importlib.util.find_spec("ensurepip") is None,
    reason="stdlib `python -m venv` needs ensurepip to bootstrap pip; absent on uv-managed pythons",
)
def test_ensure_venv_creates_real_venv(tmp_path):
    """Real, offline: a throwaway venv is genuinely created (stdlib/pip path); its python runs."""
    venv = tmp_path / "venv"
    py = inst.ensure_venv(venv)  # installer defaults to "pip" (stdlib venv)
    _assert_real_venv_python_runs(venv, py)


@pytest.mark.slow
@pytest.mark.skipif(shutil.which("uv") is None, reason="uv not installed")
def test_ensure_venv_uv_creates_real_venv(tmp_path):
    """Real, offline: `uv venv` genuinely creates a usable venv (no pip needed)."""
    venv = tmp_path / "venv"
    py = inst.ensure_venv(venv, installer="uv")
    _assert_real_venv_python_runs(venv, py)
