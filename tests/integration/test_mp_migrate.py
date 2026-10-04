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


CLEAN_SYNC = "  Gitignored:     0  (would remove)\n  Missing:        0  (would remove)\n"


def _clean_runner():
    def run(cmd):
        if "sync" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout=CLEAN_SYNC, stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    return MempalaceRunner(binary="mempalace", runner=run)


def test_migration_splits_verbatim_and_says_index_not_checked(tmp_path):
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
    # Verification runs on a working copy, so the index is explicitly not checked (GH #22):
    # said out loud rather than a misleading STALE/UNVERIFIED from syncing the wrong path.
    assert result.conformant is True
    assert "index not checked during migrate verification" in result.note


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


def test_check_dir_resolves_store_from_entity_root_and_syncs_real_path(tmp_path):
    """Non-default palace root: check_dir(entity=...) derives the store under
    data_roots.mempalace, not ~/.mempalace; index sync is opt-out for working copies."""
    from mneme.mempalace import conform
    from tests.fixtures import entity_for

    calls = []

    def run(cmd):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout=CLEAN_SYNC, stderr="")

    runner = MempalaceRunner(binary="mempalace", runner=run)
    saga = tmp_path / "wc" / "saga"
    (saga / "docs" / "chapters").mkdir(parents=True)
    (saga / ".mneme").mkdir()
    (saga / ".mneme" / "mempalace.yaml").write_text(
        SAGA_AUTHORITY + "store:\n  alias: saga\n"
    )
    root = tmp_path / "myroot"
    entity = entity_for(tmp_path / "campaigns", mempalace=root)

    conform.check_dir(saga, runner=runner, entity=entity)
    sync = next(c for c in calls if "sync" in c)
    assert str(root / "palaces" / "saga") in sync
    assert not any(".mempalace" in a for a in sync)

    calls.clear()
    conform.check_dir(saga, runner=runner, entity=entity, check_index=False)
    assert not [c for c in calls if "sync" in c]
