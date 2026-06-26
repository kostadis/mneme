"""Issue 0007 integration test: proposal branches surface as pending, then merged."""

from __future__ import annotations

import subprocess

import pytest

from mneme.mempalace import proposals
from tests.fixtures import make_campaigns


def _git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def _ok(*args, cwd=None):
    out = _git(*args, cwd=cwd)
    assert out.returncode == 0, out.stderr


@pytest.fixture
def repo(tmp_path):
    if _git("--version").returncode != 0:
        pytest.skip("git not available")
    remote = tmp_path / "remote.git"
    _ok("init", "--bare", "-b", "main", str(remote))
    active = tmp_path / "active"
    _ok("clone", str(remote), str(active))
    make_campaigns(active)
    _ok("-C", str(active), "add", "-A")
    _ok("-C", str(active), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "init")
    _ok("-C", str(active), "push", "-u", "origin", "main")
    return active


def _push_proposal(active, branch="mneme/bootstrap-full"):
    _ok("-C", str(active), "checkout", "-b", branch)
    (active / "full" / "newdoc.md").write_text("# New\n")
    _ok("-C", str(active), "add", "-A")
    _ok("-C", str(active), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "propose")
    _ok("-C", str(active), "push", "-u", "origin", branch)
    _ok("-C", str(active), "checkout", "main")


def test_pending_then_merged(repo):
    _push_proposal(repo)

    pending = proposals.list_proposals(repo)
    assert len(pending) == 1
    p = pending[0]
    assert p.branch == "mneme/bootstrap-full" and p.merged is False
    assert "full" in p.campaigns
    assert "git merge origin/mneme/bootstrap-full" in p.todo_line()

    # adopt it (the manual Gate 2), then it shows as merged → safe to delete
    _ok("-C", str(repo), "merge", "origin/mneme/bootstrap-full")
    after = {x.branch: x for x in proposals.list_proposals(repo)}
    assert after["mneme/bootstrap-full"].merged is True
    assert "git push origin --delete" in after["mneme/bootstrap-full"].todo_line()
