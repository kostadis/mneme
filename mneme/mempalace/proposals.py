"""Surface mneme-created proposal branches as a to-do list (issue 0007).

Read-only git: lists `mneme/*` branches on the campaigns repo's origin and classifies
each as **pending** (not yet merged into the active checkout → offer the merge) or
**merged** (already integrated → offer the delete). Honest by construction (it reads
the remote, never asserts) and degrades independently — no origin / fetch failure
yields an empty list, never a wedged status (Principle VI).
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

GitRunner = Callable[[list[str]], "subprocess.CompletedProcess[str]"]
BRANCH_PREFIX = "mneme/"
_REMOTE_GLOB = "refs/remotes/origin/mneme"


def _run_git(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        return subprocess.CompletedProcess(cmd, 127, stdout="", stderr="git not found")


@dataclass(frozen=True)
class Proposal:
    branch: str  # e.g. "mneme/bootstrap-obelisk"
    merged: bool
    campaigns: tuple[str, ...]

    def todo_line(self) -> str:
        if self.merged:
            return (
                f"  {self.branch:30} merged    "
                f"→ safe to delete: git push origin --delete {self.branch}"
            )
        touches = ", ".join(self.campaigns) or "—"
        return (
            f"  {self.branch:30} pending   touches: {touches:20} "
            f"→ git merge origin/{self.branch}"
        )


def _git(repo: Path, *args: str, runner: GitRunner) -> subprocess.CompletedProcess[str]:
    return runner(["git", "-C", str(repo), *args])


def list_proposals(
    repo: Path, *, fetch: bool = True, runner: GitRunner = _run_git
) -> list[Proposal]:
    """mneme/* proposal branches on origin, classified merged/pending vs the checkout HEAD."""
    if _git(repo, "rev-parse", "--git-dir", runner=runner).returncode != 0:
        return []  # not a git repo → nothing to surface
    if _git(repo, "remote", "get-url", "origin", runner=runner).returncode != 0:
        return []  # no origin → no proposals to integrate
    if fetch:
        _git(repo, "fetch", "origin", "--quiet", runner=runner)  # best-effort; ignore failure

    refs = _git(
        repo, "for-each-ref", "--format=%(refname:short)", _REMOTE_GLOB, runner=runner
    )
    proposals: list[Proposal] = []
    for short in refs.stdout.splitlines():
        short = short.strip()
        if not short:
            continue
        branch = short[len("origin/") :] if short.startswith("origin/") else short
        merged = (
            _git(repo, "merge-base", "--is-ancestor", short, "HEAD", runner=runner).returncode == 0
        )
        campaigns: tuple[str, ...] = ()
        if not merged:
            diff = _git(repo, "diff", "--name-only", f"HEAD...{short}", runner=runner)
            tops = {line.split("/", 1)[0] for line in diff.stdout.splitlines() if "/" in line}
            campaigns = tuple(sorted(tops))
        proposals.append(Proposal(branch=branch, merged=merged, campaigns=campaigns))
    return proposals


def format_todo(proposals: list[Proposal]) -> list[str]:
    """Render the TODO block; empty list if there is nothing outstanding."""
    if not proposals:
        return []
    lines = ["", "TODO — proposals awaiting integration:"]
    for p in sorted(proposals, key=lambda x: (x.merged, x.branch)):
        lines.append(p.todo_line())
    return lines
