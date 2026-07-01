"""005 integration — `status` (conform.report) spans declared trees and is read-only."""

from __future__ import annotations

import subprocess

from mneme.mempalace import conform
from mneme.mempalace.runner import MempalaceRunner
from tests.fixtures import entity_for, entity_for_trees, make_campaigns, make_simple_campaign


def runner_clean() -> MempalaceRunner:
    def run(cmd):
        if len(cmd) > 1 and cmd[1] == "sync":
            return subprocess.CompletedProcess(cmd, 0, stdout="CLEAN", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    return MempalaceRunner(binary="mempalace", runner=run)


def _snapshot_mtimes(*roots):
    seen = {}
    for root in roots:
        for p in root.rglob("*"):
            seen[p] = p.stat().st_mtime_ns
    return seen


def test_status_spans_two_trees(tmp_path):
    # SC-001 — one status run lists campaigns from both trees.
    monorepo = make_campaigns(tmp_path / "monorepo")  # full, ignore-only, bare1/2/3
    toee_tree = tmp_path / "toee"
    make_simple_campaign(toee_tree, "toee")

    report = conform.report(entity_for_trees(monorepo, toee_tree), runner=runner_clean())
    campaigns = {r.campaign for r in report.rows}
    assert {"full", "toee"} <= campaigns


def test_status_is_read_only(tmp_path):
    # SC-005 — discovery/status write nothing to any tree.
    monorepo = make_campaigns(tmp_path / "monorepo")
    toee_tree = tmp_path / "toee"
    make_simple_campaign(toee_tree, "toee")
    before = _snapshot_mtimes(monorepo, toee_tree)

    conform.report(entity_for_trees(monorepo, toee_tree), runner=runner_clean())

    after = _snapshot_mtimes(monorepo, toee_tree)
    assert before == after, "status must not modify any campaign tree"


def test_scalar_status_parity(tmp_path):
    # US2/SC-002 — scalar config produces the same campaigns as the 1-element list form.
    root = make_campaigns(tmp_path / "campaigns")
    scalar = {r.campaign for r in conform.report(entity_for(root), runner=runner_clean()).rows}
    listed = {r.campaign for r in conform.report(entity_for_trees(root), runner=runner_clean()).rows}
    assert scalar == listed
