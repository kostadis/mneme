"""T041/T042: undeclared-corpus status row, and the wing-editing commands on corpus campaigns."""

from __future__ import annotations

from dataclasses import replace

import pytest
import yaml
from typer.testing import CliRunner

from mneme.mempalace import authority, bringup, conform, publish, render
from mneme.mempalace import bootstrap as bootstrap_mod
from mneme.mempalace import cli as mpcli
from mneme.mempalace import migrate as migrate_mod
from mneme.mempalace import recipe as recipe_mod
from mneme.mempalace.corpus_guard import CorpusRefusal
from mneme.mempalace.models import (
    FAIL_STATES,
    ConformanceReport,
    ConformanceRow,
    KindDef,
    MigrationPlan,
    MigrationStep,
    State,
)
from tests.fixtures import entity_for, make_campaigns
from tests.fixtures.corpus_campaign import corpus_world, tree_snapshot

CLI = CliRunner()


def _git_must_not_run(cmd):  # noqa: ARG001
    raise AssertionError("a refusal must happen before any clone")


# ── T041 ──────────────────────────────────────────────────────────────────────


def test_undeclared_state_is_not_a_failure_even_strict():
    assert State.CORPUS_UNDECLARED not in FAIL_STATES
    row = ConformanceRow("c", "corpus", State.CORPUS_UNDECLARED, note="UNDECLARED (owed)")
    rep = ConformanceReport((row, ConformanceRow("d", "corpus", State.CORPUS_UNDECLARED)))
    assert rep.exit_code() == 0 and rep.exit_code(strict=True) == 0


def test_wing_model_campaign_gets_an_undeclared_row_and_keeps_its_other_rows(tmp_path):
    root = make_campaigns(tmp_path / "campaigns")
    ent = entity_for(root, mempalace=tmp_path / "mp")
    rep = conform.report(ent, campaign="full")
    rows = {r.dimension: r for r in rep.for_campaign("full")}
    row = rows["corpus"]
    assert row.state is State.CORPUS_UNDECLARED and row.state not in FAIL_STATES
    assert "mneme corpus init full" in row.note and "UNDECLARED" in row.note
    assert {"recipe", "render", "index"} <= set(rows)  # wing-model rows are unaffected
    assert conform.format_row(row).startswith("todo")
    only = ConformanceReport(tuple(r for r in rep.rows if r.dimension == "corpus"))
    assert only.exit_code() == 0 and only.exit_code(strict=True) == 0


def test_declared_corpus_has_no_undeclared_row(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    rep = conform.report(w.entity, "corp", runner=w.runner)
    assert State.CORPUS_UNDECLARED not in {r.state for r in rep.rows}


# ── T042 ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def w(tmp_path, monkeypatch):
    world = corpus_world(tmp_path, monkeypatch)
    monkeypatch.setattr(mpcli, "_load_or_exit", lambda _c: world.entity)
    return world


def test_bootstrap_refuses_a_corpus_campaign(w):
    before = tree_snapshot(w.camp)
    with pytest.raises(CorpusRefusal, match=r"mp bootstrap.*corpus authority"):
        bootstrap_mod.bootstrap(w.entity, "corp", git_runner=_git_must_not_run)
    res = CLI.invoke(mpcli.app, ["bootstrap", "corp"])
    assert res.exit_code != 0 and "bootstrap" in res.output and "corpus" in res.output
    assert tree_snapshot(w.camp) == before


def test_consolidate_refuses_with_the_same_message(w):
    with pytest.raises(CorpusRefusal, match="corpus campaign"):
        bootstrap_mod.consolidate_config("corp", w.camp, recipe_mod.current())


def test_migrate_refuses_even_a_dry_run(w, tmp_path):
    import json

    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"campaign": "corp", "approved_by_human": True,
                                "steps": [{"op": "reindex", "args": {}}]}))
    before = tree_snapshot(w.camp)
    for extra in ([], ["--dry-run"]):
        res = CLI.invoke(mpcli.app, ["migrate", "corp", "--plan", str(plan), *extra])
        assert res.exit_code != 0
        assert "migrate" in res.output and "edit wings" in res.output
    mplan = MigrationPlan("corp", (MigrationStep("reindex", {}),), approved_by_human=True)
    with pytest.raises(CorpusRefusal, match="edit wings"):
        migrate_mod.apply_plan(mplan, w.camp)
    assert tree_snapshot(w.camp) == before


def test_adopt_only_moves_recipe_version(w):
    auth = w.camp / ".mneme" / "mempalace.yaml"
    auth.write_text(auth.read_text().replace('"3.0.0"', '"2.0.0"'))
    written, _ = publish.adopt_in_place(w.entity, "corp")
    assert auth in written
    doc = yaml.safe_load(auth.read_text())
    assert doc["recipe_version"] == recipe_mod.current().version
    assert "wings" not in doc and "extra_exclusions" not in doc
    authority.load(w.camp, mempalace_root=w.store.parent.parent)  # still a valid authority


def _recipe_with_kind(monkeypatch, name):
    rec = recipe_mod.current()
    grown = replace(rec, kinds=(*rec.kinds, KindDef(name, "reference")))
    monkeypatch.setattr(publish._recipe, "current", lambda: grown)
    return grown


def _declare_campaign_kind(w, name):
    p = w.camp / ".mneme" / "corpus.yaml"
    p.write_text(p.read_text() + f"campaign_kinds:\n  {name}:\n    dirs: [docs/{name}]\n")


def test_adopting_a_recipe_that_shadows_a_campaign_kind_writes_nothing(w, monkeypatch):
    _declare_campaign_kind(w, "lore")
    _recipe_with_kind(monkeypatch, "lore")
    before = tree_snapshot(w.camp)
    with pytest.raises(CorpusRefusal, match="shadowed-kind"):
        publish.adopt_in_place(w.entity, "corp")
    with pytest.raises(CorpusRefusal, match="shadowed-kind"):
        publish.adopt(w.entity, "corp", git_runner=_git_must_not_run)
    res = CLI.invoke(mpcli.app, ["adopt", "corp", "--here", "--confirm"])
    assert res.exit_code != 0 and "shadowed-kind" in res.output
    assert tree_snapshot(w.camp) == before


def test_publish_preview_reports_shadowed_kind(w, monkeypatch):
    _declare_campaign_kind(w, "lore")
    _recipe_with_kind(monkeypatch, "lore")
    (plan,) = publish.preview(w.entity)
    assert "shadowed-kind" in plan.line()


def test_faces_and_render_check_use_the_corpus_render(w):
    written = bringup.render_existing_faces(w.entity, "corp")
    cfg_yaml = next(p for p in written if p == w.camp / "config" / "config.yaml")
    mp = yaml.safe_load(cfg_yaml.read_text())["mempalace"]
    assert "canon_wings" in mp and "canon_wing" not in mp

    cfg = authority.load(w.camp, mempalace_root=w.store.parent.parent)
    render.write_all(cfg, recipe_mod.current(), w.camp)
    res = CLI.invoke(mpcli.app, ["render", "corp", "--check"])
    assert res.exit_code == 0 and "coherent" in res.output
    p = w.camp / ".mneme" / "corpus.yaml"
    p.write_text(p.read_text() + "# touched\n")  # the corpus render stamps corpus.yaml's hash
    res = CLI.invoke(mpcli.app, ["render", "corp", "--check"])
    assert res.exit_code != 0 and "STALE-RENDER" in res.output
