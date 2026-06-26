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
    authority.write(_cfg(tmp_path), c)
    loaded = authority.load(c)
    assert loaded.store is not None
    assert loaded.store.alias == "saga"
    assert loaded.store.path.is_absolute()


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
