"""mneme's private working copy of the campaigns repo (FR-018, Principle IV).

All writes to campaign data happen in this clone — never in the GM's active
checkout. Changes propagate through version control (a proposal branch the campaign
owner adopts by merging/pulling). The working copy holds no authority: it is
discardable and re-cloneable (the Brick Test).
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from pathlib import Path

GitRunner = Callable[[list[str]], "subprocess.CompletedProcess[str]"]


class WorkingCopyError(Exception):
    """A git operation in the working copy failed."""


def _run_git(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True)


def default_state_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "mneme" / "campaigns-work"


def origin_url(repo: Path, runner: GitRunner = _run_git) -> str | None:
    """The `origin` remote URL of a checkout (used to clone the working copy)."""
    out = runner(["git", "-C", str(repo), "remote", "get-url", "origin"])
    return out.stdout.strip() if out.returncode == 0 else None


class WorkingCopy:
    """A git clone mneme writes into, then pushes as a proposal branch."""

    def __init__(self, path: Path, runner: GitRunner = _run_git):
        self.path = path
        self.runner = runner

    def _git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        out = self.runner(["git", "-C", str(self.path), *args])
        if check and out.returncode != 0:
            detail = (out.stderr or out.stdout or "").strip()
            raise WorkingCopyError(f"git {' '.join(args)} failed: {detail}")
        return out

    @classmethod
    def clone(
        cls, remote: str, dest: Path, runner: GitRunner = _run_git
    ) -> WorkingCopy:
        """Clone ``remote`` into ``dest`` (or fetch if already cloned)."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        if (dest / ".git").is_dir():
            wc = cls(dest, runner)
            wc._git("fetch", "origin")
            return wc
        out = runner(["git", "clone", remote, str(dest)])
        if out.returncode != 0:
            raise WorkingCopyError(f"git clone {remote} failed: {out.stderr.strip()}")
        return cls(dest, runner)

    def checkout_branch(self, branch: str, base: str = "HEAD") -> None:
        self._git("checkout", "-B", branch, base)

    def commit_all(self, message: str) -> bool:
        """Stage everything and commit. Returns False if there was nothing to commit."""
        self._git("add", "-A")
        status = self._git("status", "--porcelain")
        if not status.stdout.strip():
            return False
        self._git(
            "-c", "user.name=mneme", "-c", "user.email=mneme@local", "commit", "-m", message
        )
        return True

    def push(self, branch: str) -> None:
        self._git("push", "-u", "origin", branch)
