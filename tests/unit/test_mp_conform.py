"""US2 unit tests (T017): conformance states + disposition classification."""

from __future__ import annotations

import subprocess

from mneme.mempalace import conform
from mneme.mempalace.models import State
from mneme.mempalace.runner import MempalaceRunner
from tests.fixtures import entity_for, make_campaigns


def runner_clean():
    def run(cmd):
        if cmd[1] == "sync":
            return subprocess.CompletedProcess(cmd, 0, stdout="CLEAN", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    return MempalaceRunner(binary="mempalace", runner=run)


def _states(report, campaign):
    return {r.dimension: r.state for r in report.for_campaign(campaign)}


def test_full_is_conformant(tmp_path):
    root = make_campaigns(tmp_path / "campaigns")
    report = conform.report(entity_for(root), campaign="full", runner=runner_clean())
    st = _states(report, "full")
    assert st["recipe"] == State.CONFORMANT
    assert st["render"] == State.CONFORMANT
    assert st["index"] == State.BUILT
    assert report.exit_code() == 0


def test_missing_config_is_reported_not_failed(tmp_path):
    root = make_campaigns(tmp_path / "campaigns")
    report = conform.report(entity_for(root), campaign="bare1", runner=runner_clean())
    rows = report.for_campaign("bare1")
    assert rows[0].state == State.MISSING_CONFIG
    assert rows[0].ok is True  # not a failure (FR-006)


def test_version_behind_is_pending_upgrade(tmp_path):
    root = make_campaigns(tmp_path / "campaigns")
    auth = root / "full" / ".mneme" / "mempalace.yaml"
    auth.write_text(auth.read_text().replace('recipe_version: "1.0.0"', 'recipe_version: "0.9.0"'))
    report = conform.report(entity_for(root), campaign="full", runner=runner_clean())
    recipe_row = next(r for r in report.for_campaign("full") if r.dimension == "recipe")
    assert recipe_row.state == State.DIVERGENT_PENDING
    assert recipe_row.ok is True  # "upgrade available, not yet adopted" is legitimate


def test_undispositioned_scaffold_is_a_failure(tmp_path):
    root = make_campaigns(tmp_path / "campaigns")
    # Replace full's wings with a non-standard single wing + no disposition for it.
    auth = root / "full" / ".mneme" / "mempalace.yaml"
    auth.write_text(
        'campaign: full\nrecipe_version: "1.0.0"\n'
        "wings:\n  - {name: weird, source: '.', trust: reference, rooms: []}\n"
    )
    report = conform.report(entity_for(root), campaign="full", runner=runner_clean())
    recipe_row = next(r for r in report.for_campaign("full") if r.dimension == "recipe")
    assert recipe_row.state == State.DIVERGENT_UNDISPOSITIONED
    assert recipe_row.ok is False  # needs a decision → FAIL
    assert report.exit_code() == 1


def test_deliberate_disposition_clears_the_failure(tmp_path):
    root = make_campaigns(tmp_path / "campaigns")
    auth = root / "full" / ".mneme" / "mempalace.yaml"
    auth.write_text(
        'campaign: full\nrecipe_version: "1.0.0"\n'
        "wings:\n  - {name: weird, source: '.', trust: reference, rooms: []}\n"
        "dispositions:\n  - {divergence: scaffold.nomatch, kind: deliberate, "
        "rationale: 'single-wing on purpose', recorded: '2026-06-25'}\n"
    )
    report = conform.report(entity_for(root), campaign="full", runner=runner_clean())
    recipe_row = next(r for r in report.for_campaign("full") if r.dimension == "recipe")
    assert recipe_row.state == State.DIVERGENT_DELIBERATE
    assert recipe_row.ok is True
    assert "single-wing on purpose" in recipe_row.note


def test_invalid_config_isolated_in_report(tmp_path):
    root = make_campaigns(tmp_path / "campaigns")
    (root / "ignore-only" / ".mneme").mkdir()
    (root / "ignore-only" / ".mneme" / "mempalace.yaml").write_text("wings: []\n")
    report = conform.report(entity_for(root), runner=runner_clean())
    bad = next(r for r in report.for_campaign("ignore-only"))
    assert bad.state == State.INVALID_CONFIG and bad.ok is False
    # full still reported fine alongside
    assert _states(report, "full")["recipe"] == State.CONFORMANT
