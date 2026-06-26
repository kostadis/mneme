"""US5 integration test (T032): approved plan splits a bible verbatim; result verified;
incomplete migration is never reported healthy."""

from __future__ import annotations

import subprocess

from mneme.mempalace import migrate
from mneme.mempalace.models import MigrationPlan, MigrationStep
from mneme.mempalace.runner import MempalaceRunner

SAGA_AUTHORITY = """\
campaign: saga
recipe_version: "1.0.0"
wings:
  - {name: narrative, source: docs/chapters, trust: authoritative, rooms: []}
  - {name: saga, source: ".", trust: reference, rooms: []}
"""


def _clean_runner():
    def run(cmd):
        if cmd[1] == "sync":
            return subprocess.CompletedProcess(cmd, 0, stdout="CLEAN", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    return MempalaceRunner(binary="mempalace", runner=run)


def test_migration_splits_verbatim_and_verifies(tmp_path):
    saga = tmp_path / "saga"
    saga.mkdir()
    original = "# Chapter 1\nThe vault opens.\n\n# Chapter 2\nThe long dark.\n"
    (saga / "bible.md").write_text(original)

    plan = MigrationPlan(
        campaign="saga",
        approved_by_human=True,
        steps=(
            MigrationStep("split", {"src": "bible.md", "into": "docs/chapters"}),
            MigrationStep("write_authority", {"content": SAGA_AUTHORITY}),
            MigrationStep("reindex", {"wing": "narrative"}),
        ),
    )
    result = migrate.migrate_in_dir(plan, saga, runner=_clean_runner())

    # verbatim: chapters concatenate back to the original (SC-010)
    chapters = sorted((saga / "docs" / "chapters").glob("chapter_*.md"))
    assert "".join(c.read_text() for c in chapters) == original
    # FR-026: the ACTUAL result is verified and conforms
    assert result.conformant is True
    assert "verified" in result.note


def test_incomplete_migration_is_not_reported_healthy(tmp_path):
    saga = tmp_path / "saga"
    saga.mkdir()
    # a plan that touches nothing meaningful and leaves no authority
    plan = MigrationPlan(
        campaign="saga", approved_by_human=True, steps=(MigrationStep("reindex", {"wing": "x"}),)
    )
    result = migrate.migrate_in_dir(plan, saga, runner=_clean_runner())
    assert result.conformant is False
    assert "INCOMPLETE" in result.note  # missing authority caught by verification
