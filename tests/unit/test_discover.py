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


def test_symlinked_child_is_not_a_campaign(tmp_path):
    # GH #35 — `is_dir()` follows symlinks, so an unrelated link under the campaigns root
    # (e.g. ~/campaigns/mnt -> /mnt/) was discovered as a campaign and walked.
    t1 = tmp_path / "t1"
    make_simple_campaign(t1, "alpha")
    outside = tmp_path / "outside"
    make_simple_campaign(outside, "not-a-campaign")
    (t1 / "mnt").symlink_to(outside)
    refs = discover.discover(entity_for_trees(t1))
    assert [r.name for r in refs] == ["alpha"]


def test_wing_walk_does_not_follow_symlinks_out_of_the_campaign(tmp_path):
    # GH #35 — the wing walk used rglob, which follows symlinks; a link inside a campaign
    # pulled unrelated mempalace.yaml files (potentially the whole filesystem) into wing_dirs.
    t1 = tmp_path / "t1"
    camp = make_simple_campaign(t1, "alpha")
    (camp / "notes").mkdir()
    (camp / "notes" / "mempalace.yaml").write_text("palace: alpha\n")

    outside = tmp_path / "outside"
    (outside / "deep").mkdir(parents=True)
    (outside / "deep" / "mempalace.yaml").write_text("palace: elsewhere\n")
    (camp / "escape").symlink_to(outside)

    wing_dirs = discover.discover(entity_for_trees(t1))[0].wing_dirs
    assert camp / "notes" in wing_dirs
    assert all(outside not in d.parents for d in wing_dirs)


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


def test_ref_for_dir_builds_ref_from_path(tmp_path):
    # GH #27 — --dir resolves an explicit workspace; tree = parent.
    t1 = tmp_path / "t1"
    camp = make_simple_campaign(t1, "toee")
    ref = discover.ref_for_dir(entity_for_trees(t1), camp)
    assert ref.name == "toee" and ref.path == camp and ref.tree == t1


def test_ref_for_dir_missing_errors(tmp_path):
    with pytest.raises(discover.DiscoveryError):
        discover.ref_for_dir(entity_for_trees(tmp_path), tmp_path / "nope")


def test_resolve_dir_wins_over_ambiguous_name(tmp_path):
    # GH #27 — --dir bypasses the ambiguity guard: name in both trees, but --dir picks one.
    t1, t2 = tmp_path / "t1", tmp_path / "t2"
    a = make_simple_campaign(t1, "toee")
    make_simple_campaign(t2, "toee")
    e = entity_for_trees(t1, t2)
    with pytest.raises(discover.DiscoveryError):
        discover.resolve(e, "toee")  # ambiguous by name
    assert discover.resolve(e, "toee", a).path == a  # --dir resolves it


def test_resolve_name_when_no_dir(tmp_path):
    t1 = tmp_path / "t1"
    make_simple_campaign(t1, "alpha")
    assert discover.resolve(entity_for_trees(t1), "alpha").name == "alpha"
