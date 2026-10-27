"""Quickstart scenario 1 (US1): the palace holds exactly the curated files (T023, T024, T025)."""

from __future__ import annotations

import json
import os

from mneme.mempalace import bringup, corpus_record, refresh, render
from mneme.mempalace import recipe as recipe_mod
from tests.fixtures.corpus_campaign import (
    DECLARED,
    DECOYS,
    corpus_world,
    tree_snapshot,
    write,
)


def _render_and_refresh(w, **kw):
    cfg = _load(w)
    render.write_all(cfg, recipe_mod.current(), w.camp)
    return refresh.refresh(w.entity, campaign="corp", runner=w.runner, **kw)


def _load(w):
    from mneme.mempalace import authority

    return authority.load(w.camp, mempalace_root=w.store.parent.parent)


def test_palace_holds_exactly_the_six_declared_files(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    (res,) = _render_and_refresh(w)
    assert not res.failed, res.error
    assert w.source_rels() == set(DECLARED)  # six files, not one decoy
    assert not (set(DECOYS) & w.source_rels())
    assert {r["wing"] for r in w.sources()} == {"npcs", "summaries", "grounding"}
    # docs/party.md is declared as party and grounding; mined_as puts it in exactly one wing
    assert w.wing_of("docs/party.md") == {"grounding"}
    assert sum(1 for r in w.sources() if r["source_file"].endswith("docs/party.md")) == 1


def test_a_new_undeclared_file_adds_nothing(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    _render_and_refresh(w)
    before = w.sources()
    write(w.camp, "docs/new_generated/y.md")
    (res,) = refresh.refresh(w.entity, campaign="corp", runner=w.runner)
    assert not res.failed
    assert w.sources() == before


def test_refresh_never_runs_a_plain_mine_of_the_root(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    _render_and_refresh(w)
    mines = [ln for ln in w.log_lines() if " mine " in f" {ln} " and "--help" not in ln]
    assert mines and all("--files-from" in ln and "--wing" in ln for ln in mines)


def test_refresh_writes_only_the_toc_and_gitignore_in_the_campaign(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    render.write_all(_load(w), recipe_mod.current(), w.camp)  # render is allowed to write
    refresh.refresh(w.entity, campaign="corp", runner=w.runner)  # settle the first-time writes
    write(w.camp, "docs/npcs/b.md")  # a content change inside the corpus
    before = tree_snapshot(w.camp)
    (res,) = refresh.refresh(w.entity, campaign="corp", runner=w.runner)
    assert not res.failed
    after = tree_snapshot(w.camp)
    changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
    assert changed <= {".mneme/corpus.toc.json"}


def test_first_refresh_changes_only_toc_and_gitignore(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    before = tree_snapshot(w.camp)
    (res,) = refresh.refresh(w.entity, campaign="corp", runner=w.runner)
    assert not res.failed, res.error
    after = tree_snapshot(w.camp)
    changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
    assert changed == {".mneme/corpus.toc.json", ".gitignore"}


def test_repointed_symlink_replaces_the_old_generation(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    # grounding/current -> gen1 now, gen2 later (a grounding promotion)
    for gen in ("gen1", "gen2"):
        write(w.camp, f"docs/grounding/{gen}/world_state.md", f"# world {gen}\n")
        write(w.camp, f"docs/grounding/{gen}/planning.md", f"# planning {gen}\n")
    cur = w.camp / "docs" / "grounding" / "current"
    cur.symlink_to("gen1")
    (w.camp / ".mneme" / "corpus.yaml").write_text(
        "campaign: corp\nkinds:\n  grounding:\n"
        "    files: [docs/grounding/current/world_state.md, docs/grounding/current/planning.md]\n"
    )
    _render_and_refresh(w)
    assert w.source_rels() == {"docs/grounding/gen1/world_state.md",
                               "docs/grounding/gen1/planning.md"}
    rec = corpus_record.read(w.store)
    assert rec.files["docs/grounding/current/world_state.md"]["target"] == (
        "docs/grounding/gen1/world_state.md"
    )
    cur.unlink()
    cur.symlink_to("gen2")
    (dry,) = refresh.refresh(w.entity, campaign="corp", runner=w.runner, dry_run=True)
    assert "replaced 2 re-pointed files" in dry.line() and "gen2" in dry.line()
    assert w.source_rels() == {"docs/grounding/gen1/world_state.md",
                               "docs/grounding/gen1/planning.md"}  # a dry run changes nothing
    (res,) = refresh.refresh(w.entity, campaign="corp", runner=w.runner)
    assert not res.failed and "replaced 2 re-pointed files" in res.line()
    assert w.source_rels() == {"docs/grounding/gen2/world_state.md",
                               "docs/grounding/gen2/planning.md"}


def test_bringup_from_corpus_yaml_alone_mines_the_resolved_corpus(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch, authority=False)  # like out-of-the-abyss
    assert not (w.camp / ".mneme" / "mempalace.yaml").exists()
    report = bringup.bringup(
        w.entity, "corp", runner=w.runner, config_json=tmp_path / "config.json", do_backup=False
    )
    assert report.ready, [(s.name, s.state, s.note) for s in report.steps]
    assert [s.name for s in report.steps] == [
        "configure", "render_faces", "provision", "first_mine", "backup"
    ]
    assert w.source_rels() == set(DECLARED)  # SC-003
    auth = (w.camp / ".mneme" / "mempalace.yaml").read_text()
    assert "wings" not in auth and "alias: corp" in auth
    assert "4.0.0" in auth
    cfg = json.loads((w.camp / ".mcp.json").read_text())
    assert "mempalace" in cfg["mcpServers"]
    assert not any(
        " mine " in f" {ln} " and "--files-from" not in ln and "--help" not in ln
        for ln in w.log_lines()
    )
    assert os.path.exists(w.store / "mneme-corpus-mined.json")


def test_first_mine_into_a_missing_store_forgets_nothing(tmp_path, monkeypatch):
    # the real `forget` refuses a palace that does not exist yet (found by the real-binary e2e)
    w = corpus_world(tmp_path, monkeypatch)
    assert not w.store.exists()
    monkeypatch.setattr(w.runner, "sources", lambda palace=None, wing=None: None)  # real: rc 1
    (res,) = _render_and_refresh(w)
    assert not res.failed, res.error
    assert not any(" forget " in f" {ln} " for ln in w.log_lines())


def _declare(w, body):
    (w.camp / ".mneme" / "corpus.yaml").write_text(body)


def _mined(w):
    """Record entries for files that were embedded (a skipped file's entry says why instead)."""
    return {p for p, e in corpus_record.read(w.store).files.items() if "skipped" not in e}


def _skips_json(monkeypatch, *entries):
    monkeypatch.setenv(
        "MNEME_STUB_MINE_SKIPS_JSON",
        json.dumps([{"path": p, "reason": r, "detail": d} for p, r, d in entries]),
    )


def test_exactly_the_listed_same_named_file_is_dropped_from_the_record(tmp_path, monkeypatch):
    """Two same-named files in one kind: the JSON list names exactly one (A2)."""
    w = corpus_world(tmp_path, monkeypatch)
    write(w.camp, "docs/s/001/session-summary.md", "one")
    write(w.camp, "docs/s/002/session-summary.md", "two")
    _declare(w, "campaign: corp\nkinds:\n  summaries:\n    dirs: [docs/s]\n")
    _skips_json(monkeypatch, ("docs/s/001/session-summary.md", "too_large", "900 chunks"))
    _render_and_refresh(w)
    assert _mined(w) == {"docs/s/002/session-summary.md"}


def test_skip_of_a_root_file_does_not_drop_a_same_named_nested_one(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    write(w.camp, "a.md", "one")
    write(w.camp, "sub/a.md", "two")
    _declare(w, "campaign: corp\nkinds:\n  summaries:\n    files: [a.md]\n    dirs: [sub]\n")
    _skips_json(monkeypatch, ("a.md", "too_large", ""))
    _render_and_refresh(w)
    assert _mined(w) == {"sub/a.md"}


def test_skip_path_is_not_a_suffix_match(tmp_path, monkeypatch):
    """`sub/a.md` in the list must not also drop `x/sub/a.md`."""
    w = corpus_world(tmp_path, monkeypatch)
    write(w.camp, "sub/a.md", "one")
    write(w.camp, "x/sub/a.md", "two")
    _declare(w, "campaign: corp\nkinds:\n  summaries:\n    dirs: [sub, x]\n")
    _skips_json(monkeypatch, ("sub/a.md", "symlink", ""))
    _render_and_refresh(w)
    assert _mined(w) == {"x/sub/a.md"}


def test_listed_skips_are_gaps_and_not_recorded_as_mined(tmp_path, monkeypatch):
    """Missing / unsupported / unknown-code entries are reported with path + reason (C2, C4)."""
    w = corpus_world(tmp_path, monkeypatch)
    write(w.camp, "cx/gone.md", "one")
    write(w.camp, "cx/odd.md", "three")
    write(w.camp, "cx/ok.md", "two")
    _declare(w, "campaign: corp\nkinds:\n  summaries:\n    dirs: [cx]\n")
    _skips_json(
        monkeypatch,
        ("cx/gone.md", "missing", "file not found"),
        ("cx/odd.md", "some_future_code", "who knows"),
    )
    (res,) = _render_and_refresh(w)
    assert {(n.name, n.kind) for _, n in res.skips} == {
        ("cx/gone.md", "missing"), ("cx/odd.md", "other")
    }
    assert any("cx/gone.md" in ln and "file not found" in ln for ln in res.warnings())
    assert _mined(w) == {"cx/ok.md"}


def test_stdout_text_notices_are_ignored_by_corpus_mining(tmp_path, monkeypatch):
    """Skip detection reads the JSON list only: a text SKIP line alone changes nothing."""
    w = corpus_world(tmp_path, monkeypatch)
    write(w.camp, "cx/a.md", "one")
    _declare(w, "campaign: corp\nkinds:\n  summaries:\n    dirs: [cx]\n")
    monkeypatch.setenv("MNEME_STUB_MINE_SKIPS", "  SKIP: cx/a.md (not a regular file)")
    (res,) = _render_and_refresh(w)
    assert not res.skips
    assert set(corpus_record.read(w.store).files) == {"cx/a.md"}


def test_missing_or_garbled_skips_json_records_nothing_and_warns(tmp_path, monkeypatch):
    for mode in ("missing", "garbled"):
        w = corpus_world(tmp_path / mode, monkeypatch)
        write(w.camp, "cx/a.md", "one")
        _declare(w, "campaign: corp\nkinds:\n  summaries:\n    dirs: [cx]\n")
        monkeypatch.setenv("MNEME_STUB_SKIPS_OUT", mode)
        (res,) = _render_and_refresh(w)
        assert not res.failed, res.error
        assert corpus_record.read(w.store) is None, mode
        assert any("--skips-json" in ln for ln in res.warnings()), mode


def test_repoint_does_not_delete_a_file_another_kind_still_mines(tmp_path, monkeypatch):
    """current.md -> chapters/ch9.md re-pointed to ch10: ch9 stays mined by `chapters` (A4)."""
    w = corpus_world(tmp_path, monkeypatch)
    for n in ("ch9", "ch10"):
        write(w.camp, f"docs/chapters/{n}.md", f"# {n}\n")
    (w.camp / "docs" / "current.md").symlink_to("chapters/ch9.md")
    _declare(
        w,
        "campaign: corp\nkinds:\n  summaries:\n    dirs: [docs/chapters]\n"
        "  npcs:\n    files: [docs/current.md]\n    mined_as: true\n",
    )
    _render_and_refresh(w)
    (w.camp / "docs" / "current.md").unlink()
    (w.camp / "docs" / "current.md").symlink_to("chapters/ch10.md")
    (res,) = refresh.refresh(w.entity, campaign="corp", runner=w.runner)
    assert not res.failed, res.error
    assert w.source_rels() == {"docs/chapters/ch9.md", "docs/chapters/ch10.md"}
    assert w.wing_of("docs/chapters/ch9.md") == {"summaries"}
    assert w.wing_of("docs/chapters/ch10.md") == {"npcs"}


def test_bringup_with_an_unresolvable_declaration_writes_nothing(tmp_path, monkeypatch):
    """Structurally valid but resolves to nothing (empty dir): refuse before any write (A5)."""
    w = corpus_world(tmp_path, monkeypatch, authority=False)
    (w.camp / "docs" / "empty").mkdir()
    _declare(w, "campaign: corp\nkinds:\n  npcs:\n    dirs: [docs/empty]\n")
    before = tree_snapshot(w.camp)
    report = bringup.bringup(
        w.entity, "corp", runner=w.runner, config_json=tmp_path / "config.json", do_backup=False
    )
    assert not report.ready
    assert [(s.name, s.state) for s in report.steps] == [
        ("configure", "skipped"), ("first_mine", "failed")
    ]
    assert "empty-corpus" in report.steps[1].note
    assert tree_snapshot(w.camp) == before
    assert not (tmp_path / "config.json").exists()


def test_bringup_validates_with_the_recipe_the_authority_carries(tmp_path, monkeypatch):
    """r2 D2: an authority on a kinds-less recipe is refused BEFORE any write (first_mine would
    load that recipe and fail recipe-no-kinds), not after files were rendered."""
    w = corpus_world(tmp_path, monkeypatch)
    (w.camp / ".mneme" / "mempalace.yaml").write_text(
        'campaign: corp\nrecipe_version: "2.0.0"\nstore:\n  alias: corp\n'
    )
    before = tree_snapshot(w.camp)
    report = bringup.bringup(
        w.entity, "corp", runner=w.runner, config_json=tmp_path / "config.json", do_backup=False
    )
    assert not report.ready
    assert [(s.name, s.state) for s in report.steps] == [
        ("configure", "skipped"), ("first_mine", "failed")
    ]
    assert "recipe-no-kinds" in report.steps[1].note
    assert tree_snapshot(w.camp) == before


def test_dry_run_refuses_an_invalid_corpus_like_the_real_run(tmp_path, monkeypatch):
    """r2 D3: --dry-run must not say 'would configure' for a declaration the real run refuses."""
    w = corpus_world(tmp_path, monkeypatch, authority=False)
    _declare(w, "campaign: corp\nkinds:\n  nonsense: {}\n")
    kw = dict(runner=w.runner, config_json=tmp_path / "config.json", do_backup=False)
    real = bringup.bringup(w.entity, "corp", **kw)
    dry = bringup.bringup(w.entity, "corp", dry_run=True, **kw)
    assert not real.ready and not dry.ready
    assert [(s.name, s.state, s.note) for s in dry.steps] == [
        (s.name, s.state, s.note) for s in real.steps
    ]
