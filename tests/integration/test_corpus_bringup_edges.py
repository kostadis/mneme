"""Code-review round 3 on bring-up: TOC snapshot freshness, clean recipe errors, one recipe,
and the empty former-wings record written as soon as the store is known empty."""

from __future__ import annotations

import pytest

from mneme.corpus import config as cconfig
from mneme.corpus import resolve as cresolve
from mneme.corpus import toc as _toc
from mneme.mempalace import authority, backup, bringup, former_wings, provision, render
from mneme.mempalace import recipe as recipe_mod
from mneme.mempalace.runner import MempalaceError
from tests.fixtures.corpus_campaign import corpus_world, write


def _bring(w, tmp_path, **kw):
    return bringup.bringup(
        w.entity, "corp", runner=w.runner, config_json=tmp_path / "config.json",
        do_backup=False, **kw,
    )


def _fail_first_mine(monkeypatch):
    def boom(*a, **k):
        raise MempalaceError("embedder down")

    monkeypatch.setattr(provision, "first_mine", boom)


def test_toc_snapshot_reflects_the_render_s_own_file_changes(tmp_path, monkeypatch):
    # G1: a stamped leftover wing render under a declared dir is deleted by the corpus render;
    # a failed first mine must not leave a TOC that still lists it.
    w = corpus_world(tmp_path, monkeypatch, authority=False)
    rec = recipe_mod.current()
    root_yaml = (w.camp / "docs" / "npcs" / "mempalace.yaml")
    write(w.camp, "docs/npcs/mempalace.yaml", f"{render.STAMP_PREFIX} abc; do-not-edit\nx: 1\n")
    assert root_yaml.exists()
    _fail_first_mine(monkeypatch)
    report = _bring(w, tmp_path)
    assert not report.ready
    assert not root_yaml.exists()  # the render deleted the leftover
    ccfg = cconfig.load(w.camp, rec)
    fresh = _toc.build(cresolve.resolve(ccfg, w.camp, rec), ccfg, rec)
    assert _toc.verify(w.camp, fresh).ok, _toc.verify(w.camp, fresh)


def test_bringup_reports_a_recipe_error_cleanly(tmp_path, monkeypatch):
    # G2: the authority carries a recipe major this host does not have
    w = corpus_world(tmp_path, monkeypatch)
    (w.camp / ".mneme" / "mempalace.yaml").write_text(
        'campaign: corp\nrecipe_version: "99.0.0"\nstore:\n  alias: corp\n'
    )
    for dry in (True, False):
        report = _bring(w, tmp_path, dry_run=dry)
        assert not report.ready
        step = report.steps[-1]
        assert step.name == "first_mine" and step.state == "failed"
        assert "99" in step.note


def test_bringup_renders_with_the_recipe_the_authority_carries(tmp_path, monkeypatch):
    # G3: one recipe serves validation, render and mine — the authority's
    w = corpus_world(tmp_path, monkeypatch)
    seen = []
    real = render.render_faces

    def spy(cfg, recipe, *a, **k):
        seen.append(recipe.version)
        return real(cfg, recipe, *a, **k)

    monkeypatch.setattr(render, "render_faces", spy)
    report = _bring(w, tmp_path)
    assert report.ready
    assert seen == [recipe_mod.load("4.0.0").version]


def test_a_failed_first_bringup_still_leaves_the_empty_record_and_a_rerun_keeps_it(
    tmp_path, monkeypatch
):
    # G5
    w = corpus_world(tmp_path, monkeypatch, authority=False)
    assert not w.store.exists()
    real = provision.first_mine
    _fail_first_mine(monkeypatch)
    assert not _bring(w, tmp_path).ready
    rec = former_wings.read(w.store)
    assert rec is not None and rec.authoritative() == frozenset()
    monkeypatch.setattr(provision, "first_mine", real)
    assert _bring(w, tmp_path).ready  # the re-run: store now exists, record must persist
    rec = former_wings.read(w.store)
    assert rec is not None and rec.authoritative() == frozenset()


def test_a_failed_regenerate_still_leaves_the_empty_record(tmp_path, monkeypatch):
    # G5
    w = corpus_world(tmp_path, monkeypatch)
    cfg = authority.load(w.camp, mempalace_root=w.store.parent.parent)
    render.write_all(cfg, recipe_mod.current(), w.camp)
    w.store.mkdir(parents=True)
    _fail_first_mine(monkeypatch)
    monkeypatch.setattr(backup._provision, "first_mine", provision.first_mine)
    with pytest.raises(MempalaceError):
        backup.regenerate(w.entity, "corp", runner=w.runner)
    rec = former_wings.read(w.store)
    assert rec is not None and rec.authoritative() == frozenset()
