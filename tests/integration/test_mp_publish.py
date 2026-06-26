"""US3 integration test (T025): publish pushes a proposal branch; active checkout
is byte-unchanged (FR-018 / SC-009). Uses real git over a local bare remote."""

from __future__ import annotations

import subprocess

import pytest

from mneme.mempalace import publish
from tests.fixtures import entity_for, make_campaigns


def _git(*args: str, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def _git_ok(*args: str, cwd=None) -> None:
    out = _git(*args, cwd=cwd)
    assert out.returncode == 0, out.stderr


@pytest.fixture
def campaigns_repo(tmp_path):
    """A bare remote + an 'active checkout' with campaigns committed to main."""
    if _git("--version").returncode != 0:
        pytest.skip("git not available")
    remote = tmp_path / "remote.git"
    _git_ok("init", "--bare", "-b", "main", str(remote))
    active = tmp_path / "active"
    _git_ok("clone", str(remote), str(active))
    make_campaigns(active)
    # put `full` one version behind so publish has a real change to propose
    auth = active / "full" / ".mneme" / "mempalace.yaml"
    auth.write_text(auth.read_text().replace('recipe_version: "1.0.0"', 'recipe_version: "0.9.0"'))
    _git_ok("-C", str(active), "add", "-A")
    _git_ok("-C", str(active), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "init")
    _git_ok("-C", str(active), "push", "-u", "origin", "main")
    return remote, active


def test_publish_pushes_branch_and_leaves_active_checkout_untouched(campaigns_repo, tmp_path):
    remote, active = campaigns_repo
    before = _git("-C", str(active), "status", "--porcelain").stdout
    before_head = _git("-C", str(active), "rev-parse", "HEAD").stdout

    branch, plans = publish.publish(entity_for(active), state_dir=tmp_path / "work")

    assert branch == "mneme/recipe-1.0.0"
    # the proposal branch exists on the remote
    assert _git("-C", str(remote), "rev-parse", "--verify", branch).returncode == 0
    # SC-009: the active checkout is byte-for-byte unchanged by mneme
    assert _git("-C", str(active), "status", "--porcelain").stdout == before
    assert _git("-C", str(active), "rev-parse", "HEAD").stdout == before_head
    # the working copy carries the upgraded authority
    work_auth = (tmp_path / "work" / "full" / ".mneme" / "mempalace.yaml").read_text()
    assert 'recipe_version: 1.0.0' in work_auth or 'recipe_version: "1.0.0"' in work_auth
    assert any(p.campaign == "full" for p in plans)
