"""005 integration — membership end-to-end across discovery, find, and status (US4, US5)."""

from __future__ import annotations

import subprocess

import pytest

from hypostasis.models import MnemeIdentity
from mneme.mempalace import conform, discover, ownership
from mneme.mempalace.models import State
from mneme.mempalace.ownership import OwnerState
from tests.fixtures import entity_for_trees, make_simple_campaign

ID_A = MnemeIdentity(id="aaaaaaaa-0000-0000-0000-000000000000", label="fleet-a")
ID_B = MnemeIdentity(id="bbbbbbbb-0000-0000-0000-000000000000", label="fleet-b")


def runner_clean():
    def run(cmd):
        if len(cmd) > 1 and cmd[1] == "sync":
            return subprocess.CompletedProcess(cmd, 0, stdout="CLEAN", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    from mneme.mempalace.runner import MempalaceRunner

    return MempalaceRunner(binary="mempalace", runner=run)


def test_discover_marks_owner_state(tmp_path):
    t = tmp_path / "t1"
    mine = make_simple_campaign(t, "mine")
    ownership.write_owner(mine, ID_A)
    make_simple_campaign(t, "fresh")
    states = {r.name: r.owner_state for r in discover.discover(entity_for_trees(t, identity=ID_A))}
    assert states["mine"] is OwnerState.OWNED
    assert states["fresh"] is OwnerState.UNINTEGRATED


def test_find_excludes_foreign_resolves_owned(tmp_path):
    t1, t2 = tmp_path / "t1", tmp_path / "t2"
    a = make_simple_campaign(t1, "toee")
    ownership.write_owner(a, ID_A)
    b = make_simple_campaign(t2, "toee")
    ownership.write_owner(b, ID_B)  # foreign — must be excluded, not ambiguous
    assert discover.find(entity_for_trees(t1, t2, identity=ID_A), "toee").path == a


def test_find_foreign_only_reports_foreign(tmp_path):
    t = tmp_path / "t1"
    f = make_simple_campaign(t, "toee")
    ownership.write_owner(f, ID_B)
    with pytest.raises(discover.DiscoveryError) as ei:
        discover.find(entity_for_trees(t, identity=ID_A), "toee")
    assert "foreign-owned" in str(ei.value)


def test_two_owned_same_name_still_ambiguous(tmp_path):
    t1, t2 = tmp_path / "t1", tmp_path / "t2"
    for tree in (t1, t2):
        ownership.write_owner(make_simple_campaign(tree, "toee"), ID_A)
    with pytest.raises(discover.DiscoveryError) as ei:
        discover.find(entity_for_trees(t1, t2, identity=ID_A), "toee")
    assert "ambiguous" in str(ei.value)


def test_status_reports_membership(tmp_path):
    # SC-006 — status surfaces owned / foreign / un-integrated, read-only.
    t = tmp_path / "t1"
    ownership.write_owner(make_simple_campaign(t, "owned"), ID_A)
    ownership.write_owner(make_simple_campaign(t, "foreign"), ID_B)
    make_simple_campaign(t, "fresh")
    report = conform.report(entity_for_trees(t, identity=ID_A), runner=runner_clean())
    owner = {r.campaign: r for r in report.rows if r.dimension == "owner"}
    assert owner["owned"].state is State.OWNED
    assert owner["foreign"].state is State.FOREIGN and ID_B.id in owner["foreign"].observed
    assert owner["fresh"].state is State.UNINTEGRATED
    # foreign/un-integrated are surfaced but not hard failures
    assert all(r.ok for r in owner.values())


def test_unverifiable_without_identity(tmp_path):
    t = tmp_path / "t1"
    ownership.write_owner(make_simple_campaign(t, "claimed"), ID_A)
    report = conform.report(entity_for_trees(t), runner=runner_clean())  # no identity
    owner = next(r for r in report.rows if r.dimension == "owner" and r.campaign == "claimed")
    assert owner.state is State.UNVERIFIABLE
