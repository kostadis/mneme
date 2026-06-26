"""Issue 0007 unit tests: graceful degradation + TODO formatting."""

from __future__ import annotations

from mneme.mempalace import proposals
from mneme.mempalace.proposals import Proposal


def test_non_git_dir_yields_no_proposals(tmp_path):
    # Not a git repo → empty, never a crash (Principle VI).
    assert proposals.list_proposals(tmp_path, fetch=False) == []


def test_format_todo_distinguishes_pending_and_merged():
    items = [
        Proposal("mneme/recipe-2.0.0", merged=False, campaigns=("full", "obelisk")),
        Proposal("mneme/adopt-saga-1.0.0", merged=True, campaigns=()),
    ]
    lines = proposals.format_todo(items)
    text = "\n".join(lines)
    assert "TODO — proposals awaiting integration:" in text
    assert "pending" in text and "full, obelisk" in text
    assert "merged" in text and "git push origin --delete mneme/adopt-saga-1.0.0" in text


def test_format_todo_empty_when_nothing_outstanding():
    assert proposals.format_todo([]) == []
