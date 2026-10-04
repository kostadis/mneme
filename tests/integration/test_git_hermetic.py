"""The suite must not touch an inherited repository: under `git rebase --exec` git exports
GIT_DIR, and the git-driving tests once committed into — and pushed from — the real repo."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GIT_TESTS = ["tests/integration/test_mp_publish.py", "tests/integration/test_mp_proposals.py"]


def _git(repo: Path, *args: str) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True, env=env
    ).stdout


def test_git_tests_ignore_inherited_git_dir(tmp_path):
    sentinel = tmp_path / "sentinel"
    sentinel.mkdir()
    _git(sentinel, "init", "-q")
    _git(sentinel, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
         "--allow-empty", "-m", "sentinel")
    refs_before = _git(sentinel, "for-each-ref")
    config_before = (sentinel / ".git" / "config").read_text()

    env = {**os.environ, "GIT_DIR": str(sentinel / ".git"), "GIT_WORK_TREE": str(sentinel)}
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *GIT_TESTS],
        cwd=ROOT, env=env, capture_output=True, text=True,
    )
    assert out.returncode == 0, out.stdout[-2000:] + out.stderr[-2000:]
    assert _git(sentinel, "for-each-ref") == refs_before
    assert (sentinel / ".git" / "config").read_text() == config_before
