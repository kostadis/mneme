"""US1 unit tests (T013): wing mining order, skip missing, isolate invalid, idempotent."""

from __future__ import annotations

import subprocess

from mneme.mempalace import refresh
from mneme.mempalace.runner import MempalaceRunner
from tests.fixtures import entity_for, make_campaigns


def fake_runner(fail_on: str | None = None):
    calls: list[list[str]] = []

    def run(cmd):
        calls.append(cmd)
        rc = 1 if (fail_on and fail_on in " ".join(cmd)) else 0
        return subprocess.CompletedProcess(cmd, rc, stdout="", stderr="boom" if rc else "")

    run.calls = calls
    return MempalaceRunner(binary="mempalace", runner=run), calls


def test_refresh_mines_full_subscopes_before_root(tmp_path):
    root = make_campaigns(tmp_path / "campaigns")
    entity = entity_for(root)
    runner, calls = fake_runner()
    results = refresh.refresh(entity, campaign="full", runner=runner)
    assert len(results) == 1 and not results[0].failed and not results[0].skipped
    mine_targets = [c[2] for c in calls if c[1] == "mine"]
    # the two doc sub-scopes are mined before the campaign root ("." wing)
    root_idx = next(i for i, t in enumerate(mine_targets) if t == str(root / "full"))
    chap_idx = next(i for i, t in enumerate(mine_targets) if t.endswith("docs/chapters"))
    assert chap_idx < root_idx


def test_refresh_skips_campaign_without_wings(tmp_path):
    root = make_campaigns(tmp_path / "campaigns")
    entity = entity_for(root)
    runner, _ = fake_runner()
    results = {r.campaign: r for r in refresh.refresh(entity, runner=runner)}
    assert results["bare1"].skipped is True
    assert results["ignore-only"].skipped is True  # only a .mempalaceignore, no wings
    assert results["full"].skipped is False


def test_refresh_isolates_a_failing_campaign(tmp_path):
    root = make_campaigns(tmp_path / "campaigns")
    entity = entity_for(root)
    runner, _ = fake_runner(fail_on="chapters")  # mining the narrative wing fails
    results = {r.campaign: r for r in refresh.refresh(entity, runner=runner)}
    assert results["full"].failed is True and "rc 1" in results["full"].error
    # other campaigns are unaffected (skipped, not failed)
    assert results["bare2"].skipped is True


def test_refresh_dry_run_plans_without_real_mine(tmp_path):
    root = make_campaigns(tmp_path / "campaigns")
    entity = entity_for(root)
    runner, calls = fake_runner()
    results = refresh.refresh(entity, campaign="full", dry_run=True, runner=runner)
    assert results[0].dry_run and all("--dry-run" in c for c in calls if c[1] == "mine")
