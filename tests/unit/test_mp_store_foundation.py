"""003 foundational unit tests (T008): store-pointer authority, the four faces, health."""

from __future__ import annotations

import json

import pytest
import yaml

from mneme.mempalace import authority, health, recipe, render
from mneme.mempalace.authority import AuthorityError
from mneme.mempalace.models import (
    CampaignMempalaceConfig,
    StorePointer,
    StoreState,
    Wing,
)


def _cfg(tmp_path, campaign="saga"):
    store = StorePointer(alias=campaign, path=tmp_path / ".mempalace" / "palaces" / campaign)
    return CampaignMempalaceConfig(
        campaign=campaign,
        recipe_version="1.0.0",
        wings=(
            Wing("narrative", "docs/chapters", "authoritative", ()),
            Wing(campaign, ".", "reference", ()),
        ),
        store=store,
    )


# ── store-pointer authority ─────────────────────────────────────────────────


def test_authority_roundtrips_store_pointer(tmp_path):
    c = tmp_path / "saga"
    (c / "docs" / "chapters").mkdir(parents=True)
    root = tmp_path / ".mempalace"
    authority.write(_cfg(tmp_path), c)
    loaded = authority.load(c, mempalace_root=root)
    assert loaded.store is not None
    assert loaded.store.alias == "saga"
    assert loaded.store.path == root / "palaces" / "saga"


# ── 006 — the store location is derived, never tracked (US2) ────────────────────


def _write_authority(tmp_path, campaign="saga", store_block="store:\n  alias: saga\n"):
    c = tmp_path / campaign
    (c / "docs" / "chapters").mkdir(parents=True)
    (c / ".mneme").mkdir(parents=True, exist_ok=True)
    (c / ".mneme" / "mempalace.yaml").write_text(
        f"campaign: {campaign}\n"
        "recipe_version: '2.0.0'\n"
        f"{store_block}"
        "wings:\n"
        "  - name: narrative\n    source: docs/chapters\n    trust: authoritative\n    rooms: []\n"
        f"  - name: {campaign}\n    source: .\n    trust: reference\n    rooms: []\n"
    )
    return c


def test_to_yaml_never_emits_a_store_path(tmp_path):
    # FR-010 / SC-005 — the guarantee is structural: no serializer for the path exists.
    text = authority.to_yaml(_cfg(tmp_path))
    doc = yaml.safe_load(text)
    assert doc["store"] == {"alias": "saga"}
    assert "path" not in text


def test_two_hosts_resolve_different_paths_from_identical_bytes(tmp_path):
    # FR-011 / SC-003 — the GH #51 ping-pong is gone by construction: nothing to disagree on.
    c = _write_authority(tmp_path)
    before = (c / ".mneme" / "mempalace.yaml").read_bytes()

    host_a = authority.load(c, mempalace_root=tmp_path / "hostA" / ".mempalace")
    host_b = authority.load(c, mempalace_root=tmp_path / "hostB" / ".mempalace")

    assert host_a.store.path == tmp_path / "hostA" / ".mempalace" / "palaces" / "saga"
    assert host_b.store.path == tmp_path / "hostB" / ".mempalace" / "palaces" / "saga"
    assert host_a.store.alias == host_b.store.alias == "saga"
    assert (c / ".mneme" / "mempalace.yaml").read_bytes() == before  # neither host rewrote it


def test_write_is_a_fixed_point_under_either_host(tmp_path):
    # FR-017 — identical input bytes produce identical output bytes regardless of $HOME.
    c = _write_authority(tmp_path)
    a = authority.load(c, mempalace_root=tmp_path / "hostA")
    b = authority.load(c, mempalace_root=tmp_path / "hostB")
    assert authority.to_yaml(a) == authority.to_yaml(b)


def test_authority_without_store_block_still_loads(tmp_path):
    # 002-era compatibility — no store block at all remains valid; require_store gates bring-up.
    c = _write_authority(tmp_path, store_block="")
    loaded = authority.load(c, mempalace_root=tmp_path / "mp")
    assert loaded.store is None
    with pytest.raises(AuthorityError):
        authority.require_store(loaded)


# ── 006 — legacy `store.path` in an existing authority (US3) ────────────────────


def test_legacy_path_equal_to_derived_loads_and_is_flagged(tmp_path):
    # FR-013 — accepted, and reported as owed cleanup rather than silently tolerated.
    root = tmp_path / "mp"
    derived = root / "palaces" / "saga"
    c = _write_authority(tmp_path, store_block=f"store:\n  alias: saga\n  path: {derived}\n")
    loaded = authority.load(c, mempalace_root=root)
    assert loaded.store.path == derived
    assert authority.has_legacy_store_path(c) is True


def test_legacy_path_different_from_derived_is_fatal(tmp_path):
    # FR-014 — a conflicting path may name a real store full of real content. Fail closed
    # on EVERY operation rather than silently abandoning it.
    c = _write_authority(
        tmp_path,
        store_block="store:\n  alias: saga\n  path: /home/someone-else/.mempalace/palaces/saga\n",
    )
    with pytest.raises(AuthorityError) as ei:
        authority.load(c, mempalace_root=tmp_path / "mp")
    msg = "; ".join(ei.value.problems)
    assert "/home/someone-else/.mempalace/palaces/saga" in msg   # names the tracked location
    assert str(tmp_path / "mp" / "palaces" / "saga") in msg      # and the derived one
    assert "remove the `path:` key" in msg                       # and the remedy


def test_legacy_path_via_symlink_is_not_a_conflict(tmp_path):
    # FR-011a — a sanctioned filesystem redirect must not read as a mismatch.
    root = tmp_path / "mp"
    (root / "palaces").mkdir(parents=True)
    real = tmp_path / "elsewhere" / "saga"
    real.mkdir(parents=True)
    (root / "palaces" / "saga").symlink_to(real)
    c = _write_authority(tmp_path, store_block=f"store:\n  alias: saga\n  path: {real}\n")
    loaded = authority.load(c, mempalace_root=root)  # must not raise
    assert loaded.store.alias == "saga"


def test_legacy_path_with_trailing_separator_is_not_a_conflict(tmp_path):
    root = tmp_path / "mp"
    derived = root / "palaces" / "saga"
    c = _write_authority(tmp_path, store_block=f"store:\n  alias: saga\n  path: {derived}/\n")
    assert authority.load(c, mempalace_root=root).store.path == derived


def test_authority_without_legacy_path_reports_no_cleanup(tmp_path):
    c = _write_authority(tmp_path)
    authority.load(c, mempalace_root=tmp_path / "mp")
    assert authority.has_legacy_store_path(c) is False


def test_require_store_refuses_missing_pointer(tmp_path):
    c = tmp_path / "old"
    (c / "docs").mkdir(parents=True)
    cfg = CampaignMempalaceConfig(
        campaign="old", recipe_version="1.0.0",
        wings=(Wing("old", ".", "reference", ()),), store=None,
    )
    with pytest.raises(AuthorityError):
        authority.require_store(cfg)


# ── the four faces ───────────────────────────────────────────────────────────


def test_cli_pointer_root_wing_carries_palace(tmp_path):
    cfg = _cfg(tmp_path)
    arts = {str(a.target): a for a in render.render(cfg, recipe.current())}
    root = arts["mempalace.yaml"].content  # the root wing (source ".")
    assert "palace: saga" in root
    # a non-root wing yaml does NOT carry palace:
    assert "palace:" not in arts["docs/chapters/mempalace.yaml"].content


def test_config_yaml_face_merges_not_clobbers(tmp_path):
    c = tmp_path / "saga"
    c.mkdir()
    (c / "config.yaml").write_text(yaml.safe_dump({"campaign_name": "Saga", "other": 1}))
    render.render_config_yaml(_cfg(tmp_path), c)
    doc = yaml.safe_load((c / "config.yaml").read_text())
    assert doc["campaign_name"] == "Saga" and doc["other"] == 1  # preserved
    assert doc["mempalace"]["canon_wing"] == "narrative"
    assert "saga" in doc["mempalace"]["index_wings"]


def test_global_alias_face_merges_not_clobbers(tmp_path):
    cj = tmp_path / ".mempalace" / "config.json"
    cj.parent.mkdir(parents=True)
    cj.write_text(
        json.dumps({"default_palace": "chat", "palaces": {"chat": "/x/chat", "abyss": "/x/abyss"}})
    )
    render.render_global_alias(_cfg(tmp_path), cj)
    data = json.loads(cj.read_text())
    assert data["default_palace"] == "chat"  # preserved
    assert data["palaces"]["abyss"] == "/x/abyss"  # other campaign preserved (Principle VI)
    assert data["palaces"]["saga"].endswith("/palaces/saga")  # this campaign added


def test_mcp_face_points_at_store_no_hardcode(tmp_path):
    c = tmp_path / "saga"
    c.mkdir()
    (c / ".mcp.json").write_text(json.dumps({"mcpServers": {"campaign": {"type": "stdio"}}}))
    render.render_mcp(_cfg(tmp_path), c)
    data = json.loads((c / ".mcp.json").read_text())
    assert data["mcpServers"]["campaign"]["type"] == "stdio"  # other server preserved
    env = data["mcpServers"]["mempalace"]["env"]
    assert env["MEMPALACE_PALACE_PATH"].endswith("/palaces/saga")  # from the store pointer


# ── health / store inspection ────────────────────────────────────────────────


def test_health_classifies_store_files(tmp_path):
    store = tmp_path / "store"
    (store / "turbovec" / "mempalace_drawers").mkdir(parents=True)
    (store / "turbovec" / "mempalace_drawers" / "store.sqlite3").write_text("b")
    (store / "turbovec" / "mempalace_drawers" / "index.tvim").write_text("i")
    (store / "knowledge_graph.sqlite3").write_text("kg")
    (store / "chroma.sqlite3").write_text("legacy")
    ds = health.inspect(store)
    assert ds.present is True
    names = {p.name for p in ds.bindings_files}
    assert "store.sqlite3" in names and "knowledge_graph.sqlite3" in names
    assert any(p.name == "index.tvim" for p in ds.rebuildable_files)
    assert any(p.name == "chroma.sqlite3" for p in ds.legacy_files)


def test_health_missing_store(tmp_path):
    h = health.health(tmp_path / "nope")
    assert h.present is False and h.state is StoreState.MISSING and h.ok is False
