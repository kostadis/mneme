"""US4 unit tests (T033): starter scaffold selection + scatter→single-authority consolidation."""

from __future__ import annotations

from mneme.mempalace import authority, bootstrap, recipe


def test_starter_picks_single_wing_for_bare_campaign(tmp_path):
    c = tmp_path / "bare"
    c.mkdir()
    (c / "notes.md").write_text("x")
    cfg = bootstrap.starter_config("bare", c, recipe.current())
    assert [w.name for w in cfg.wings] == ["bare"]
    assert cfg.wings[0].source == "."


def test_starter_picks_three_wing_for_pipeline_campaign(tmp_path):
    c = tmp_path / "saga"
    (c / "docs" / "chapters").mkdir(parents=True)
    (c / "docs" / "distill_extractions").mkdir(parents=True)
    cfg = bootstrap.starter_config("saga", c, recipe.current())
    names = [w.name for w in cfg.wings]
    assert "narrative" in names and "chronicle" in names and "saga" in names


def test_consolidate_folds_scattered_wing_yamls(tmp_path):
    c = tmp_path / "old"
    (c / "docs" / "chapters").mkdir(parents=True)
    (c / "docs" / "chapters" / "mempalace.yaml").write_text(
        "wing: narrative\nrooms:\n- {name: chapters, description: c, keywords: [chapter]}\n"
    )
    (c / "mempalace.yaml").write_text(
        "wing: old\nrooms:\n- {name: npcs, description: n, keywords: [npc]}\n"
    )
    cfg = bootstrap.consolidate_config("old", c, recipe.current())
    by_source = {w.source: w for w in cfg.wings}
    assert by_source["docs/chapters"].name == "narrative"
    assert by_source["."].name == "old"
    # consolidated authority is itself valid (sub-scopes ordered before root)
    bootstrap.write_into(cfg, recipe.current(), c)
    reloaded = authority.load(c)
    assert {w.source for w in reloaded.wings} == {"docs/chapters", "."}
