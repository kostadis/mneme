"""US5 unit tests (T031): verbatim guard + approval gate + plan validation."""

from __future__ import annotations

import pytest

from mneme.mempalace import migrate
from mneme.mempalace.migrate import MigrationError
from mneme.mempalace.models import MigrationPlan, MigrationStep


def test_validate_rejects_unapproved_plan():
    plan = MigrationPlan(campaign="c", steps=(MigrationStep("move", {"src": "a", "dst": "b"}),))
    problems = migrate.validate_plan(plan)
    assert any("approved_by_human" in p for p in problems)


def test_validate_rejects_content_rewriting_op():
    plan = MigrationPlan(
        campaign="c",
        steps=(MigrationStep("rewrite_content", {"file": "x"}),),
        approved_by_human=True,
    )
    problems = migrate.validate_plan(plan)
    assert any("not content-preserving" in p for p in problems)


def test_apply_split_is_verbatim(tmp_path):
    bible = tmp_path / "bible.md"
    original = "# Chapter 1\nArrival at the prison.\n\n# Chapter 2\nThe escape.\n"
    bible.write_text(original)
    plan = MigrationPlan(
        campaign="c",
        steps=(MigrationStep("split", {"src": "bible.md", "into": "docs/chapters"}),),
        approved_by_human=True,
    )
    migrate.apply_plan(plan, tmp_path)

    chapters = sorted((tmp_path / "docs" / "chapters").glob("chapter_*.md"))
    assert len(chapters) == 2
    # SC-010: concatenated chapters are byte-for-byte the original
    assert "".join(c.read_text() for c in chapters) == original
    assert not bible.exists()


def test_apply_refuses_when_unapproved(tmp_path):
    (tmp_path / "a.md").write_text("x")
    plan = MigrationPlan(
        campaign="c", steps=(MigrationStep("move", {"src": "a.md", "dst": "b.md"}),)
    )
    with pytest.raises(MigrationError):
        migrate.apply_plan(plan, tmp_path)
