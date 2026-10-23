"""Corpus render (007 T020): root yaml, TOC, leftover cleanup, search face."""

from __future__ import annotations

import yaml

from mneme.corpus import toc
from mneme.mempalace import authority, recipe, render
from tests.fixtures.corpus_campaign import corpus_world, write


def _setup(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    cfg = authority.load(w.camp, mempalace_root=w.store.parent.parent)
    return w, cfg, recipe.current()


def test_root_yaml_is_stamped_with_palace_and_rooms(tmp_path, monkeypatch):
    w, cfg, rec = _setup(tmp_path, monkeypatch)
    written = render.write_all(cfg, rec, w.camp)
    assert w.camp / "mempalace.yaml" in written and toc.toc_path(w.camp) in written
    path = w.camp / "mempalace.yaml"
    assert render.read_stamp(path) is not None
    doc = yaml.safe_load(path.read_text().split("\n", 1)[1])
    assert doc["palace"] == "corp"
    names = [r["name"] for r in doc["rooms"]]
    assert {"npcs", "summary", "party", "world", "prep", "general"} <= set(names)
    assert len(names) == len(set(names))  # the union has no duplicates
    assert "wing" not in doc
    assert (w.camp / ".gitignore").read_text().count(".mneme/corpus.toc.json") == 1


def test_leftover_stamped_wing_renders_are_deleted_and_only_those(tmp_path, monkeypatch):
    w, cfg, rec = _setup(tmp_path, monkeypatch)
    stamped = f"{render.STAMP_PREFIX} abc; {render.STAMP_SUFFIX}\n"
    write(w.camp, "docs/npcs/mempalace.yaml", stamped + "wing: npcs\n")
    write(w.camp, ".mempalaceignore", stamped + "logs/\n")
    write(w.camp, "docs/summaries/mempalace.yaml", "wing: hand_written\n")  # the GM's own
    render.write_all(cfg, rec, w.camp)
    assert not (w.camp / "docs/npcs/mempalace.yaml").exists()
    assert not (w.camp / ".mempalaceignore").exists()
    assert (w.camp / "docs/summaries/mempalace.yaml").read_text() == "wing: hand_written\n"


def test_config_yaml_has_canon_wings_and_no_canon_wing(tmp_path, monkeypatch):
    w, cfg, rec = _setup(tmp_path, monkeypatch)
    (w.camp / "config.yaml").write_text("keep: me\nmempalace:\n  canon_wing: old\n")
    (w.camp / ".mneme" / "corpus.yaml").write_text(
        "campaign: corp\nkinds:\n  npcs:\n    dirs: [docs/npcs]\n"
        "  prep:\n    dirs: [docs/reviews]\n"
        "  summaries:\n    dirs: [docs/summaries]\n    trust: reference\n"
        "campaign_kinds:\n  lore:\n    files: [docs/planning.md]\n    trust: authoritative\n"
        "  extras:\n    files: [docs/world_state.md]\n    trust: reference\n"
    )
    render.render_config_yaml(cfg, w.camp, rec)
    doc = yaml.safe_load((w.camp / "config.yaml").read_text())
    assert doc["keep"] == "me"
    assert doc["mempalace"] == {
        "canon_wings": ["npcs", "lore"],  # recipe order, then campaign kinds
        "index_wings": ["summaries", "prep", "extras"],
    }
    assert "canon_wing" not in doc["mempalace"]


def test_coherent_detects_stale_toc_stamp_and_leftovers(tmp_path, monkeypatch):
    w, cfg, rec = _setup(tmp_path, monkeypatch)
    assert render.coherent(cfg, rec, w.camp)  # nothing rendered yet
    render.write_all(cfg, rec, w.camp)
    assert render.coherent(cfg, rec, w.camp) == []
    write(w.camp, "docs/npcs/new.md")  # a file added to a declared folder: TOC is stale
    assert toc.TOC_RELPATH in render.coherent(cfg, rec, w.camp)
    render.write_all(cfg, rec, w.camp)
    (w.camp / ".mneme" / "corpus.yaml").write_text(
        (w.camp / ".mneme" / "corpus.yaml").read_text() + "\n# touched\n"
    )
    assert render.coherent(cfg, rec, w.camp)  # corpus_sha256 changed: root yaml + TOC stale
    render.write_all(cfg, rec, w.camp)
    write(w.camp, "docs/x/mempalace.yaml", f"{render.STAMP_PREFIX} z; {render.STAMP_SUFFIX}\n")
    assert [p.as_posix() for p in render.coherent(cfg, rec, w.camp)] == ["docs/x/mempalace.yaml"]


def test_faces_cover_the_corpus_artifacts(tmp_path, monkeypatch):
    w, cfg, rec = _setup(tmp_path, monkeypatch)
    cj = tmp_path / "config.json"
    written = render.render_faces(cfg, rec, w.camp, cj)
    assert w.camp / "mempalace.yaml" in written and w.camp / "config.yaml" in written
    assert render.faces_coherent(cfg, w.camp, cj) == []
    (w.camp / "mempalace.yaml").write_text("palace: other\n")
    assert any("cli_pointer" in b for b in render.faces_coherent(cfg, w.camp, cj))


def test_wing_model_render_is_unchanged(tmp_path):
    from tests.fixtures import make_campaigns

    root = make_campaigns(tmp_path / "c")
    cfg = authority.load(root / "full")
    render.write_all(cfg, recipe.load(cfg.recipe_version), root / "full")
    assert render.coherent(cfg, recipe.load(cfg.recipe_version), root / "full") == []
    doc = yaml.safe_load(render.render_config_yaml(cfg, root / "full").read_text())
    assert "canon_wing" in doc["mempalace"] and "canon_wings" not in doc["mempalace"]
