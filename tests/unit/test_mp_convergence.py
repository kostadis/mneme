"""GH #24 convergence tooling: standard scaffold, consolidate fidelity, H1 faces, H2 drop-legacy."""

from __future__ import annotations

import json

import yaml

from mneme.mempalace import authority, bootstrap, bringup, health, recipe
from tests.fixtures import entity_for


def _mk(root, *subdirs):
    root.mkdir(parents=True, exist_ok=True)
    for s in subdirs:
        (root / s).mkdir(parents=True, exist_ok=True)
    return root


# ── standard scaffold (Task #2) ──────────────────────────────────────────────


def test_standard_scaffold_is_dir_filtered(tmp_path):
    rec = recipe.current()
    full = _mk(tmp_path / "a", "docs/chapters", "docs/distill_extractions", "notes/sessions",
              "notes", "summaries")
    cfg = bootstrap.starter_config("a", full, rec)
    by = {w.name: w for w in cfg.wings}
    assert set(by) == {"narrative", "chronicle", "prep", "notes", "summaries", "a"}
    assert by["narrative"].trust == "authoritative"
    assert by["chronicle"].trust == "accelerator"
    assert by["a"].trust == "reference" and by["a"].source == "."
    # root last (sub-scopes-before-root); round-trips through the validating loader cleanly
    assert cfg.wings[-1].source == "."
    authority.write(cfg, full)
    assert {w.name for w in authority.load(full).wings} == set(by)
    # a campaign with only summaries/ gets just summaries + campaign ("wire what exists")
    sparse = _mk(tmp_path / "h", "summaries")
    assert {w.name for w in bootstrap.starter_config("h", sparse, rec).wings} == {"summaries", "h"}


# ── consolidate fidelity (Task #5) ───────────────────────────────────────────


def test_consolidate_carries_trust_store_and_folded_exclusions(tmp_path):
    camp = _mk(tmp_path / "saga", "docs/chapters")
    (camp / "mempalace.yaml").write_text("wing: saga\nrooms:\n- {name: npcs, description: x}\n")
    (camp / "docs" / "chapters" / "mempalace.yaml").write_text(
        "wing: narrative\nrooms:\n- {name: chapters, description: prose}\n"
    )
    (camp / ".mempalaceignore").write_text(
        "# guards\ndocs/chapters/\nconfig.yaml\ndocs/background/\n*.pdf\n"
    )
    cfg = bootstrap.consolidate_config("saga", camp, recipe.current())
    by = {w.name: w for w in cfg.wings}
    assert by["narrative"].trust == "authoritative"  # role-derived, not forced reference
    assert by["saga"].trust == "reference"
    assert cfg.store is not None and cfg.store.alias == "saga"
    # campaign-specific globs folded; baseline + wing-source guards dropped
    assert "docs/background/" in cfg.extra_exclusions and "*.pdf" in cfg.extra_exclusions
    assert "config.yaml" not in cfg.extra_exclusions  # recipe baseline
    assert "docs/chapters/" not in cfg.extra_exclusions  # wing source (render regenerates)


# ── H1: faces-only render for an existing campaign (Task #3) ──────────────────


def test_render_existing_faces(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    root = tmp_path / "campaigns"
    camp = _mk(root / "saga", "docs/chapters")
    from mneme.mempalace.models import CampaignMempalaceConfig, StorePointer, Wing
    cfg = CampaignMempalaceConfig(
        campaign="saga", recipe_version=recipe.current().version,
        wings=(Wing("narrative", "docs/chapters", "authoritative", ()),
               Wing("saga", ".", "reference", ())),
        store=StorePointer("saga", tmp_path / "home" / ".mempalace" / "palaces" / "saga"),
    )
    authority.write(cfg, camp)
    cj = tmp_path / "home" / ".mempalace" / "config.json"
    written = bringup.render_existing_faces(entity_for(root), "saga", config_json=cj)
    assert "palace: saga" in (camp / "mempalace.yaml").read_text()          # cli pointer
    assert yaml.safe_load((camp / "config.yaml").read_text())["mempalace"]   # cg_search
    assert "saga" in json.loads(cj.read_text())["palaces"]                   # global alias
    assert (camp / ".mcp.json").exists()                                     # mcp face
    assert len(written) >= 4


# ── H2: chroma-legacy classification + drop-legacy (Task #4) ─────────────────


def _store_with_legacy(store):
    (store / "turbovec" / "mempalace_drawers").mkdir(parents=True)
    (store / "turbovec" / "mempalace_drawers" / "store.sqlite3").write_text("bind")
    (store / "turbovec" / "mempalace_drawers" / "index.tvim").write_text("idx")
    (store / "knowledge_graph.sqlite3").write_text("kg")
    (store / "chroma.sqlite3").write_text("legacy")
    (store / ".blob_seq_ids_migrated").write_text("")
    seg = store / "0daa1234-5678"
    seg.mkdir()
    (seg / "header.bin").write_text("h")
    (seg / "data_level0.bin").write_text("d")
    return store


def test_inspect_classifies_chroma_segments_and_marker(tmp_path):
    ds = health.inspect(_store_with_legacy(tmp_path / "store"))
    legacy_names = {p.name for p in ds.legacy_files}
    assert "chroma.sqlite3" in legacy_names
    assert ".blob_seq_ids_migrated" in legacy_names
    assert "0daa1234-5678" in legacy_names  # the hnswlib segment dir
    assert ds.present is True  # turbovec bindings still recognized


def test_drop_legacy_removes_chroma_preserves_bindings(tmp_path):
    store = _store_with_legacy(tmp_path / "store")
    removed = health.drop_legacy(store)
    assert len(removed) == 3
    assert not (store / "chroma.sqlite3").exists()
    assert not (store / "0daa1234-5678").exists()
    assert not (store / ".blob_seq_ids_migrated").exists()
    # bindings + index preserved
    assert (store / "turbovec" / "mempalace_drawers" / "store.sqlite3").exists()
    assert (store / "turbovec" / "mempalace_drawers" / "index.tvim").exists()
    assert health.drop_legacy(store) == []  # idempotent
