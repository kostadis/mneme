"""005 — multi-tree discovery & name resolution (US1, US2, US3)."""

from __future__ import annotations

import pytest

from mneme.mempalace import discover
from tests.fixtures import entity_for, entity_for_trees, make_simple_campaign


def test_discover_across_two_trees_deterministic(tmp_path):
    # US1 — campaigns from both trees, sorted by (name, tree). (FR-003/010)
    t1, t2 = tmp_path / "t1", tmp_path / "t2"
    make_simple_campaign(t1, "alpha")
    make_simple_campaign(t1, "beta")
    make_simple_campaign(t2, "gamma")
    refs = discover.discover(entity_for_trees(t1, t2))
    assert [r.name for r in refs] == ["alpha", "beta", "gamma"]
    assert next(r for r in refs if r.name == "alpha").tree == t1
    assert next(r for r in refs if r.name == "gamma").tree == t2


def test_discover_campaign_one_level_below_tree_root(tmp_path):
    # US1 acceptance #2 — a standalone tree whose single campaign is <tree>/toee.
    toee_tree = tmp_path / "toee"
    make_simple_campaign(toee_tree, "toee")
    refs = discover.discover(entity_for_trees(toee_tree))
    assert [r.name for r in refs] == ["toee"]
    assert refs[0].tree == toee_tree


def test_discover_empty_or_absent_tree_contributes_nothing(tmp_path):
    t1 = tmp_path / "t1"
    make_simple_campaign(t1, "alpha")
    empty = tmp_path / "empty"
    empty.mkdir()
    absent = tmp_path / "absent"  # never created — must not wedge the run (VI)
    refs = discover.discover(entity_for_trees(t1, empty, absent))
    assert [r.name for r in refs] == ["alpha"]


def test_scalar_single_tree_parity(tmp_path):
    # US2 — a scalar campaigns root yields the same refs as a 1-element list.
    root = tmp_path / "campaigns"
    make_simple_campaign(root, "alpha")
    by_scalar = discover.discover(entity_for(root))
    by_list = discover.discover(entity_for_trees(root))
    assert [r.name for r in by_scalar] == [r.name for r in by_list] == ["alpha"]


def test_find_single_match(tmp_path):
    t1 = tmp_path / "t1"
    make_simple_campaign(t1, "alpha")
    assert discover.find(entity_for_trees(t1), "alpha").path == t1 / "alpha"


def test_find_not_found_lists_trees(tmp_path):
    t1, t2 = tmp_path / "t1", tmp_path / "t2"
    t1.mkdir()
    t2.mkdir()
    with pytest.raises(discover.DiscoveryError) as ei:
        discover.find(entity_for_trees(t1, t2), "nope")
    msg = str(ei.value)
    assert "not found" in msg and str(t1) in msg and str(t2) in msg


def test_find_ambiguous_across_trees_errors(tmp_path):
    # US3 — same name under two trees must never resolve silently (FR-005).
    t1, t2 = tmp_path / "t1", tmp_path / "t2"
    make_simple_campaign(t1, "toee")
    make_simple_campaign(t2, "toee")
    with pytest.raises(discover.DiscoveryError) as ei:
        discover.find(entity_for_trees(t1, t2), "toee")
    msg = str(ei.value)
    assert "ambiguous" in msg and str(t1) in msg and str(t2) in msg
