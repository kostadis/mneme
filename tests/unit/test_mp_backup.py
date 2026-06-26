"""US3 unit tests (T018): backup selection, restore-without-re-embed, regenerate."""

from __future__ import annotations

import subprocess

from mneme.mempalace import authority, backup
from mneme.mempalace.models import CampaignMempalaceConfig, StorePointer, Wing
from mneme.mempalace.runner import MempalaceRunner
from tests.fixtures import entity_for


def _setup(tmp_path, monkeypatch, campaign="saga"):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    root = tmp_path / "campaigns"
    camp = root / campaign
    camp.mkdir(parents=True)
    store = tmp_path / "home" / ".mempalace" / "palaces" / campaign
    cfg = CampaignMempalaceConfig(
        campaign=campaign, recipe_version="1.0.0",
        wings=(Wing(campaign, ".", "reference", ()),),
        store=StorePointer(campaign, store),
    )
    authority.write(cfg, camp)
    # a real-looking store: bindings + rebuildable + legacy
    (store / "turbovec" / "mempalace_drawers").mkdir(parents=True)
    (store / "turbovec" / "mempalace_drawers" / "store.sqlite3").write_text("BINDINGS")
    (store / "turbovec" / "mempalace_drawers" / "index.tvim").write_text("idx")
    (store / "knowledge_graph.sqlite3").write_text("kg")
    (store / "chroma.sqlite3").write_text("legacy")
    return entity_for(root), store


def test_backup_includes_bindings_excludes_rebuildable_and_legacy(tmp_path, monkeypatch):
    entity, store = _setup(tmp_path, monkeypatch)
    b = backup.backup(entity, "saga")
    names = {p.name for p in b.contents}
    assert "store.sqlite3" in names and "knowledge_graph.sqlite3" in names
    assert "index.tvim" not in names and "chroma.sqlite3" not in names


def test_restore_preserves_bindings_without_re_embed(tmp_path, monkeypatch):
    entity, store = _setup(tmp_path, monkeypatch)
    backup.backup(entity, "saga")
    import shutil

    shutil.rmtree(store)  # lose the store
    restored = backup.restore(entity, "saga")
    # bindings are back; restore never re-embeds (no index.tvim restored — turbovecdb rebuilds it)
    assert (store / "turbovec" / "mempalace_drawers" / "store.sqlite3").read_text() == "BINDINGS"
    assert not (store / "turbovec" / "mempalace_drawers" / "index.tvim").exists()
    assert any(p.name == "store.sqlite3" for p in restored)


def test_regenerate_re_mines(tmp_path, monkeypatch):
    entity, store = _setup(tmp_path, monkeypatch)
    calls: list[list[str]] = []

    def run(cmd):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    backup.regenerate(entity, "saga", runner=MempalaceRunner(binary="mempalace", runner=run))
    assert any(c[0:1] == ["mempalace"] and "mine" in c for c in calls)  # re-embed happened
    assert not (store / "chroma.sqlite3").exists()  # store was cleared first
