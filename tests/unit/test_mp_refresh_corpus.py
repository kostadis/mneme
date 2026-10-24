"""Corpus refresh (007 T021, T022): re-mine on change, re-home, refusals, dry run."""

from __future__ import annotations

import json
import os

from mneme.mempalace import corpus_record, refresh, render
from mneme.mempalace import recipe as recipe_mod
from tests.fixtures.corpus_campaign import DECLARED, corpus_world


def go(w, **kw):
    (r,) = refresh.refresh(w.entity, campaign="corp", runner=w.runner, **kw)
    return r


def abs_(w, rel):
    return str((w.camp / rel).resolve())


def test_record_has_kind_sha_target_for_every_mined_file(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    assert not go(w).failed
    r = corpus_record.read(w.store)
    assert set(r.files) == set(DECLARED)
    assert r.files["docs/party.md"]["kind"] == "grounding"
    assert r.files["docs/npcs/a.md"] == {
        "kind": "npcs", "target": "docs/npcs/a.md", "sha256": r.files["docs/npcs/a.md"]["sha256"],
    }


def test_same_mtime_edit_is_forgotten_and_remined(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    go(w)
    p = w.camp / "docs/npcs/a.md"
    st = p.stat()
    p.write_text("# edited, same mtime\n")
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))
    old = corpus_record.read(w.store).files["docs/npcs/a.md"]["sha256"]
    r = go(w)
    assert r.corpus.remined == ["docs/npcs/a.md"]
    assert any(" forget " in f" {ln} " for ln in w.log_lines())
    assert corpus_record.read(w.store).files["docs/npcs/a.md"]["sha256"] != old
    assert w.source_rels() == set(DECLARED)  # still exactly one source per file
    # a no-change refresh forgets nothing
    n = len([ln for ln in w.log_lines() if " forget " in f" {ln} "])
    assert go(w).corpus.remined == []
    assert len([ln for ln in w.log_lines() if " forget " in f" {ln} "]) == n


def test_file_under_a_foreign_wing_is_rehomed(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    w.state.write_text(json.dumps([
        {"wing": "corp", "source_file": abs_(w, "docs/npcs/a.md"), "source_mtime": 1.0,
         "drawers": 1},
        {"wing": "corp", "source_file": abs_(w, "docs/campaign_state_draft.md"),
         "source_mtime": 1.0, "drawers": 1},  # undeclared: left for prune
    ]))
    r = go(w)
    assert r.corpus.rehomed == ["docs/npcs/a.md"]
    assert w.wing_of("docs/npcs/a.md") == {"npcs"}
    assert w.wing_of("docs/campaign_state_draft.md") == {"corp"}  # untouched
    assert "re-homed 1" in r.line()


def test_dry_run_lists_files_and_changes_nothing(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    w.state.write_text(json.dumps([
        {"wing": "corp", "source_file": abs_(w, "docs/npcs/a.md"), "source_mtime": 1.0,
         "drawers": 1},
    ]))
    r = go(w, dry_run=True)
    line = r.line()
    assert "PLAN" in line and "docs/npcs/a.md" in line and "docs/summaries/001.md" in line
    assert "re-homed 1" in line
    assert w.wing_of("docs/npcs/a.md") == {"corp"} and len(w.sources()) == 1
    assert not any(" mine " in f" {ln} " and "--help" not in ln for ln in w.log_lines())
    assert not (w.camp / ".mneme" / "corpus.toc.json").exists()
    assert not (w.store / corpus_record.FILENAME).exists()


def test_old_mempalace_fails_and_never_falls_back_to_wings(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    monkeypatch.setenv("MNEME_STUB_OLD", "1")
    r = go(w)
    assert r.failed and "mempalace too old for corpus mining" in r.error
    assert "--files-from" in r.error and "--skips-json" in r.error
    assert not any(" mine " in f" {ln} " and "--help" not in ln for ln in w.log_lines())


def test_mempalace_without_skips_json_fails_naming_the_flag(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    monkeypatch.setenv("MNEME_STUB_OLD", "skips")
    r = go(w)
    assert r.failed and "mempalace too old for corpus mining" in r.error
    assert "mine --skips-json" in r.error and "--files-from" not in r.error
    assert not any(" mine " in f" {ln} " and "--help" not in ln for ln in w.log_lines())


def test_invalid_corpus_mines_nothing_and_reports_findings(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    (w.camp / ".gitignore").write_text("docs/npcs/\n")
    r = go(w)
    assert r.failed and "gitignored" in r.error
    assert not any(" mine " in f" {ln} " and "--help" not in ln for ln in w.log_lines())
    assert w.sources() == []


def test_unreadable_corpus_yaml_fails_cleanly(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    (w.camp / ".mneme" / "corpus.yaml").write_text("campaign: corp\nbogus: 1\n")
    r = go(w)
    assert r.failed and "unknown-key" in r.error


def test_failed_kind_stops_the_run_and_writes_no_clean_record(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    real = w.runner.runner

    def flaky(cmd):
        if "--wing" in cmd and cmd[cmd.index("--wing") + 1] == "summaries" and "mine" in cmd:
            import subprocess

            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom")
        return real(cmd)

    w.runner.runner = flaky
    r = go(w)
    assert r.failed and "boom" in r.error
    assert w.source_rels() == {"docs/npcs/a.md"}  # npcs (recipe order) ran before the failure
    rec = corpus_record.read(w.store)
    assert set(rec.files) == {"docs/npcs/a.md"}  # only the kind that succeeded is recorded
    last = json.loads((w.store / "mneme-last-mine.json").read_text())
    assert last["status"] == "failed"


def test_unreadable_sources_do_not_stop_the_mine(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    monkeypatch.setenv("MNEME_STUB_SOURCES", "rc1")
    r = go(w)
    assert not r.failed and w.source_rels() == set(DECLARED)


def test_no_authority_is_skipped_not_mined(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch, authority=False)
    r = go(w)
    assert r.skipped and "bringup" in r.error
    assert w.sources() == []


def test_render_then_refresh_roundtrip_keeps_render_coherent(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    from mneme.mempalace import authority

    cfg = authority.load(w.camp, mempalace_root=w.store.parent.parent)
    rec = recipe_mod.current()
    render.write_all(cfg, rec, w.camp)
    go(w)
    assert render.coherent(cfg, rec, w.camp) == []  # refresh rewrote the same snapshot
