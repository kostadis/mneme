"""006 FR-016a/018 — every single-campaign route goes through ``discover.resolve``.

``find()`` only names a campaign; ``resolve()`` is the one gate for ownership and
store-alias uniqueness. These tests pin that no route (MCP tools, publish, lifecycle,
``--dir``) can reach a campaign whose alias is shared, or one owned by another mneme."""

from __future__ import annotations

import pytest

from hypostasis.models import MnemeIdentity
from mneme import lifecycle
from mneme.mcp import server
from mneme.mempalace import discover, ownership, publish
from tests.fixtures import entity_for_trees, make_simple_campaign

ID_A = MnemeIdentity(id="aaaaaaaa-0000-0000-0000-000000000000", label="fleet-a")
ID_B = MnemeIdentity(id="bbbbbbbb-0000-0000-0000-000000000000", label="fleet-b")


def _authority(camp, alias, extra_store=""):
    (camp / ".mneme").mkdir(parents=True, exist_ok=True)
    (camp / ".mneme" / "mempalace.yaml").write_text(
        f"campaign: {camp.name}\nrecipe_version: '2.0.0'\n"
        f"store:\n  alias: {alias}\n{extra_store}"
        f"wings:\n  - name: {camp.name}\n    source: .\n    trust: reference\n    rooms: []\n"
    )


def _owned(tree, name, alias, **kw):
    camp = make_simple_campaign(tree, name)
    ownership.write_owner(camp, ID_A)
    _authority(camp, alias, **kw)
    return camp


@pytest.fixture
def clashing(tmp_path):
    t = tmp_path / "t"
    a = _owned(t, "toee", "shared")
    _owned(t, "obelisk", "shared")
    return entity_for_trees(t, identity=ID_A), a


ROUTES = {
    "mcp.target_config": lambda e, c: server.target_config(e, c),
    "mcp.inventory": lambda e, c: server.inventory(e, c),
    "mcp.adopt": lambda e, c: server.adopt(e, c),
    "mcp.campaign_usage_guide": lambda e, c: server.campaign_usage_guide(e, c),
    "publish.adopt": lambda e, c: publish.adopt(e, c),
    "publish.adopt_in_place": lambda e, c: publish.adopt_in_place(e, c),
    "lifecycle._campaign_dir": lambda e, c: lifecycle._campaign_dir(e, c),
}


@pytest.mark.parametrize("route", sorted(ROUTES))
def test_route_refuses_shared_alias(clashing, route):
    entity, camp = clashing
    exc = lifecycle.LifecycleError if route.startswith("lifecycle") else discover.DiscoveryError
    before = (camp / ".mneme" / "mempalace.yaml").read_bytes()
    with pytest.raises(exc) as ei:
        ROUTES[route](entity, "toee")
    msg = str(ei.value)
    assert "shared" in msg and "toee" in msg and "obelisk" in msg
    # adopt_in_place WRITES the authority — a refused route must write nothing.
    assert (camp / ".mneme" / "mempalace.yaml").read_bytes() == before
    assert sorted(p.name for p in (camp / ".mneme").iterdir()) == ["mempalace.yaml", "owner.yaml"]


def test_dir_outside_every_tree_is_checked_against_discovered_aliases(tmp_path):
    # C2 — an out-of-tree --dir workspace is invisible to discovery, so the alias check
    # must come from its OWN authority.
    t = tmp_path / "t"
    _owned(t, "toee", "shared")
    outside = _owned(tmp_path / "elsewhere", "stray", "shared")
    entity = entity_for_trees(t, identity=ID_A)
    with pytest.raises(discover.DiscoveryError) as ei:
        discover.resolve(entity, None, outside)
    msg = str(ei.value)
    assert "shared" in msg and "toee" in msg and "stray" in msg


def test_dir_outside_every_tree_with_distinct_alias_is_fine(tmp_path):
    t = tmp_path / "t"
    _owned(t, "toee", "toee")
    outside = _owned(tmp_path / "elsewhere", "stray", "stray")
    entity = entity_for_trees(t, identity=ID_A)
    assert discover.resolve(entity, None, outside).path == outside


def test_same_campaign_via_dir_and_discovery_is_not_a_self_conflict(tmp_path):
    t = tmp_path / "t"
    a = _owned(t, "toee", "toee")
    _owned(t, "obelisk", "obelisk")
    entity = entity_for_trees(t, identity=ID_A)
    assert discover.resolve(entity, "toee").path == a
    assert discover.resolve(entity, None, a).path == a
    # A non-normalised spelling of the same path is still the same campaign.
    assert discover.resolve(entity, None, t / ".." / "t" / "toee").name == "toee"


def test_legacy_store_path_still_counts_under_non_default_palace_root(tmp_path):
    # C3 — a legacy store.path matching the derived location UNDER THIS HOST'S root loads;
    # judged against the default root it is "conflicting", the campaign drops out of the
    # alias check silently, and the clash goes undetected.
    mp = tmp_path / "mp"
    t = tmp_path / "t"
    derived = mp / "palaces" / "shared"
    _owned(t, "toee", "shared", extra_store=f"  path: {derived}\n")
    _owned(t, "obelisk", "shared")
    entity = entity_for_trees(t, identity=ID_A, mempalace=mp)
    assert discover.alias_conflicts(entity) == {"shared": ["obelisk", "toee"]}
    with pytest.raises(discover.DiscoveryError):
        discover.resolve(entity, "obelisk")
    outside = _owned(tmp_path / "x", "stray", "shared", extra_store=f"  path: {derived}\n")
    with pytest.raises(discover.DiscoveryError):
        discover.resolve(entity, None, outside)


def test_lifecycle_dir_override_refuses_foreign_owned(tmp_path):
    # C4 — `--dir` selects a workspace; it never confers ownership.
    t = tmp_path / "t"
    foreign = make_simple_campaign(t, "toee")
    ownership.write_owner(foreign, ID_B)
    entity = entity_for_trees(t, identity=ID_A)
    with pytest.raises(lifecycle.LifecycleError) as ei:
        lifecycle._campaign_dir(entity, "toee", str(foreign))
    msg = str(ei.value)
    assert "owned by " + ID_B.id in msg and "mneme identity adopt" in msg
    assert "(or pass --dir)" not in msg


def test_lifecycle_dir_override_missing_dir_is_workspace_not_found(tmp_path):
    entity = entity_for_trees(tmp_path / "t", identity=ID_A)
    with pytest.raises(lifecycle.LifecycleError, match="workspace not found"):
        lifecycle._campaign_dir(entity, "toee", str(tmp_path / "nope"))


def test_lifecycle_name_path_keeps_dir_hint(tmp_path):
    t = tmp_path / "t"
    t.mkdir()
    entity = entity_for_trees(t, identity=ID_A)
    with pytest.raises(lifecycle.LifecycleError, match=r"\(or pass --dir\)"):
        lifecycle._campaign_dir(entity, "nope")
