"""T010 — install orchestration: pins honored, order respected, fail-loud (FR-006).

The command runner is injected so the orchestration (correct pip targets, declared
order, fail-loud naming) is tested deterministically without a network. A separate
slow test exercises real venv creation. The full real install→render loop is the
container acid test (T034), not duplicated here.
"""

from __future__ import annotations

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


def make_entity(tmp_path):
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


@pytest.mark.slow
def test_ensure_venv_creates_real_venv(tmp_path):
    """Real, offline: a throwaway venv is genuinely created and its python runs."""
    venv = tmp_path / "venv"
    py = inst.ensure_venv(venv)
    assert py.exists(), "venv python should exist after creation"
    out = subprocess.run(
        [str(py), "-c", "import sys; print(sys.executable)"],
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0
    assert str(venv) in out.stdout
