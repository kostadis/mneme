"""Code-review round 4 (007): unknown/chunk-cap/skip-vocabulary handling of corpus mining."""

from __future__ import annotations

from mneme.mempalace import backup, bringup, corpus_record, mine_record, refresh
from tests.fixtures.corpus_campaign import corpus_world, write
from tests.integration.test_corpus_mining import _declare, _load, _render_and_refresh, _skips_json


def _simple(w, body="campaign: corp\nkinds:\n  summaries:\n    dirs: [cx]\n"):
    write(w.camp, "cx/a.md", "one")
    _declare(w, body)


def test_bringup_shows_corpus_warnings(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch, authority=False)
    monkeypatch.setenv("MNEME_STUB_SKIPS_OUT", "missing")
    report = bringup.bringup(
        w.entity, "corp", runner=w.runner, config_json=tmp_path / "config.json", do_backup=False
    )
    assert any("--skips-json" in ln for ln in report.warnings), report.warnings


def test_regenerate_carries_corpus_warnings(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    _render_and_refresh(w)
    monkeypatch.setenv("MNEME_STUB_SKIPS_OUT", "garbled")
    fm = backup.regenerate(w.entity, "corp", runner=w.runner)
    assert any("--skips-json" in ln for ln in fm.warnings), fm.warnings


def test_unknown_skip_list_is_not_a_clean_gaps_record(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    _simple(w)
    monkeypatch.setenv("MNEME_STUB_SKIPS_OUT", "missing")
    _render_and_refresh(w)
    from mneme.mempalace import conform

    rec = mine_record.read(w.store)
    assert rec.status != "ok" or rec.names, "unknown skip list recorded as gap-free"
    row = conform._gaps_row(
        type("R", (), {"name": "corp"})(), _load(w)
    )
    assert row.state.name != "CONFORMANT", row


def test_chunk_cap_is_mined_recorded_and_still_a_gap(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    _simple(w)
    _skips_json(monkeypatch, ("cx/a.md", "chunk_cap", "900 chunks"))
    (res,) = _render_and_refresh(w)
    assert set(corpus_record.read(w.store).files) == {"cx/a.md"}
    assert any("cx/a.md" in ln and "900 chunks" in ln for ln in res.warnings())
    assert mine_record.read(w.store).names == ["cx/a.md"]
    # converges: the next refresh does not forget and re-embed it
    n = len([ln for ln in w.log_lines() if " forget " in f" {ln} "])
    (res2,) = refresh.refresh(w.entity, campaign="corp", runner=w.runner)
    assert res2.corpus.remined == []
    assert len([ln for ln in w.log_lines() if " forget " in f" {ln} "]) == n


def test_unknown_skip_list_keeps_prior_record_entries(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    _simple(w)
    _render_and_refresh(w)
    before = corpus_record.read(w.store).files
    assert before
    monkeypatch.setenv("MNEME_STUB_SKIPS_OUT", "missing")
    refresh.refresh(w.entity, campaign="corp", runner=w.runner)
    assert corpus_record.read(w.store).files == before


def test_reason_codes_map_into_the_report_vocabulary(tmp_path, monkeypatch):
    from mneme.mempalace import mine_report

    w = corpus_world(tmp_path, monkeypatch)
    for n in ("a", "b", "c", "d"):
        write(w.camp, f"cx/{n}.md", n)
    _declare(w, "campaign: corp\nkinds:\n  summaries:\n    dirs: [cx]\n")
    _skips_json(
        monkeypatch,
        ("cx/a.md", "purge_skipped", "boom"),
        ("cx/b.md", "too_short", "tiny"),
        ("cx/c.md", "brand_new_code", "x"),
        ("cx/d.md", "write_failed", "disk"),
    )
    (res,) = _render_and_refresh(w)
    kinds = {n.name: n.kind for _, n in res.skips}
    assert kinds == {
        "cx/a.md": "purge_failed", "cx/b.md": "too_short",
        "cx/c.md": "other", "cx/d.md": "write_failed",
    }
    assert set(kinds.values()) <= set(mine_report.KINDS)
    assert any("brand_new_code" in ln for ln in res.warnings())


def _corpus_note(w):
    from mneme.mempalace import conform

    rep = conform.report(w.entity, "corp", runner=w.runner)
    row = next(r for r in rep.rows if r.dimension == "corpus")
    return row


def test_too_short_file_stays_unmined_with_its_own_remedy(tmp_path, monkeypatch):
    """GM 2026-10-24: a too_short file is still a failing UNMINED finding, but `mp refresh`
    can never fix it, so the remedy says add content or undeclare."""
    from mneme.mempalace.models import State

    w = corpus_world(tmp_path, monkeypatch)
    write(w.camp, "cx/a.md", "one")
    write(w.camp, "cx/tiny.md", "x")
    _declare(w, "campaign: corp\nkinds:\n  summaries:\n    dirs: [cx]\n")
    _skips_json(monkeypatch, ("cx/tiny.md", "too_short", "under minimum"))
    _render_and_refresh(w)
    row = _corpus_note(w)
    assert row.state is State.UNMINED, row
    assert "cx/tiny.md" in row.note
    assert "too short to index" in row.note and ".mneme/corpus.yaml" in row.note
    assert "mp refresh" not in row.note


def test_too_short_and_other_unmined_show_both_remedies(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    write(w.camp, "cx/a.md", "one")
    write(w.camp, "cx/tiny.md", "x")
    _declare(w, "campaign: corp\nkinds:\n  summaries:\n    dirs: [cx]\n")
    _skips_json(monkeypatch, ("cx/tiny.md", "too_short", "under minimum"))
    _render_and_refresh(w)
    write(w.camp, "cx/new.md", "fresh")  # declared by the dir, not yet mined
    note = _corpus_note(w).note
    assert "mneme mp refresh corp" in note and "too short to index" in note, note


def test_refresh_cli_shows_a_clean_error_when_the_capability_probe_cannot_run(
    tmp_path, monkeypatch
):
    """`supports_corpus()` raises MempalaceError when `--help` fails: a clean FAIL line, no
    traceback."""
    import subprocess

    from typer.testing import CliRunner

    from mneme.cli import app
    from mneme.mempalace.runner import MempalaceRunner

    w = corpus_world(tmp_path, monkeypatch)
    _render_and_refresh(w)

    def run(cmd):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="Traceback: boom")

    monkeypatch.setattr(
        MempalaceRunner, "for_entity", classmethod(lambda cls, entity, **kw: cls("mempalace", run))
    )
    monkeypatch.setattr("mneme.mempalace.cli._load_or_exit", lambda _c: w.entity)
    r = CliRunner().invoke(app, ["mp", "refresh", "corp"])
    assert r.exit_code != 0
    assert r.exception is None or isinstance(r.exception, SystemExit), repr(r.exception)
    out = r.output
    assert "cannot probe mempalace capabilities" in out, out
    assert "Traceback (most recent" not in out
