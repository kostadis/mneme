"""Code-review round 4 (007): unknown/chunk-cap/skip-vocabulary handling of corpus mining."""

from __future__ import annotations

import subprocess

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


def _tiny_world(tmp_path, monkeypatch, *skips):
    w = corpus_world(tmp_path, monkeypatch)
    write(w.camp, "cx/a.md", "one")
    write(w.camp, "cx/tiny.md", "x")
    _declare(w, "campaign: corp\nkinds:\n  summaries:\n    dirs: [cx]\n")
    _skips_json(monkeypatch, *skips)
    _render_and_refresh(w)
    return w


def test_too_short_file_stays_unmined_with_its_own_remedy(tmp_path, monkeypatch):
    """GM 2026-10-24: a too_short file is still a failing UNMINED finding, but `mp refresh`
    alone can never fix it, so the remedy says add content (then refresh) or undeclare."""
    from mneme.mempalace.models import State

    w = _tiny_world(tmp_path, monkeypatch, ("cx/tiny.md", "too_short", "under minimum"))
    row = _corpus_note(w)
    assert row.state is State.UNMINED, row
    assert "cx/tiny.md" in row.note
    assert "too short to index: add content (then `mneme mp refresh`) or undeclare it" in row.note
    assert "mneme mp refresh corp" not in row.note


def test_skip_status_is_stored_in_the_corpus_record_with_the_content_hash(
    tmp_path, monkeypatch
):
    w = _tiny_world(tmp_path, monkeypatch, ("cx/tiny.md", "too_short", "under minimum"))
    files = corpus_record.read(w.store).files
    assert files["cx/tiny.md"]["skipped"] == "too_short"
    assert files["cx/tiny.md"]["sha256"]
    assert "skipped" not in files["cx/a.md"]


def test_content_added_after_a_too_short_skip_goes_back_to_refresh(tmp_path, monkeypatch):
    """The skip is tied to the content hash: once the GM adds content, only a refresh can
    retry it, so status stops saying 'too short'."""
    w = _tiny_world(tmp_path, monkeypatch, ("cx/tiny.md", "too_short", "under minimum"))
    write(w.camp, "cx/tiny.md", "now there is plenty of content here")
    row = _corpus_note(w)
    assert "cx/tiny.md" in row.note
    assert "mneme mp refresh corp" in row.note, row.note
    assert "too short to index" not in row.note
    assert "changed since it was skipped as too_short" in row.note


def test_unknown_skip_list_on_a_later_refresh_keeps_the_skip_remedy(tmp_path, monkeypatch):
    w = _tiny_world(tmp_path, monkeypatch, ("cx/tiny.md", "too_short", "under minimum"))
    monkeypatch.setenv("MNEME_STUB_SKIPS_OUT", "missing")
    refresh.refresh(w.entity, campaign="corp", runner=w.runner)
    assert "too short to index" in _corpus_note(w).note


def test_every_refresh_cannot_fix_skip_has_its_own_remedy(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    names = ("large", "excl", "ext", "link", "reg", "outside", "gone", "lim")
    for n in names:
        write(w.camp, f"cx/{n}.md", n)
    _declare(w, "campaign: corp\nkinds:\n  summaries:\n    dirs: [cx]\n")
    _skips_json(
        monkeypatch,
        ("cx/large.md", "too_large", ""), ("cx/excl.md", "excluded", ""),
        ("cx/ext.md", "unsupported_ext", ""), ("cx/link.md", "symlink", ""),
        ("cx/reg.md", "not_regular", ""), ("cx/outside.md", "outside_dir", ""),
        ("cx/gone.md", "missing", ""), ("cx/lim.md", "limit", ""),
    )
    _render_and_refresh(w)
    note = _corpus_note(w).note
    for want in (
        "too large for mempalace: split it or undeclare it",
        "excluded by a mempalace.yaml exclude pattern: remove the pattern or undeclare it",
        "not a file type mempalace reads: undeclare it",
        "symlink: fix the path in .mneme/corpus.yaml",
        "not_regular: fix the path in .mneme/corpus.yaml",
        "outside_dir: fix the path in .mneme/corpus.yaml",
        "missing: fix the path in .mneme/corpus.yaml",
    ):
        assert want in note, (want, note)
    # a transient skip keeps the refresh remedy
    assert "mneme mp refresh corp" in note and "cx/lim.md" in note


def test_too_large_and_excluded_are_not_told_to_refresh(tmp_path, monkeypatch):
    w = _tiny_world(
        tmp_path, monkeypatch,
        ("cx/tiny.md", "too_large", ""), ("cx/a.md", "excluded", ""),
    )
    note = _corpus_note(w).note
    assert "split it or undeclare it" in note and "remove the pattern or undeclare it" in note
    assert "mneme mp refresh" not in note


def test_too_short_and_other_unmined_show_both_remedies(tmp_path, monkeypatch):
    w = _tiny_world(tmp_path, monkeypatch, ("cx/tiny.md", "too_short", "under minimum"))
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


def _warn_then_fail_world(tmp_path, monkeypatch):
    """Kind `npcs` mines with no usable skip list (a warning); then a changed file in a later
    kind needs a forget that fails, so the mine raises."""
    w = corpus_world(tmp_path, monkeypatch)
    _render_and_refresh(w)
    write(w.camp, "docs/planning.md", "changed content")
    monkeypatch.setenv("MNEME_STUB_SKIPS_OUT", "missing")
    monkeypatch.setenv("MNEME_STUB_FORGET", "rc1")
    return w


def test_warnings_collected_before_a_failed_mine_are_kept_on_the_error(tmp_path, monkeypatch):
    import pytest

    from mneme.mempalace.corpus_mine import mine_corpus
    from mneme.mempalace.runner import MempalaceError

    w = _warn_then_fail_world(tmp_path, monkeypatch)
    with pytest.raises(MempalaceError) as ei:
        mine_corpus(w.camp, "corp", w.store, w.runner, __import__(
            "mneme.mempalace.recipe", fromlist=["current"]).current())
    assert any("--skips-json" in ln for ln in ei.value.warnings), ei.value.warnings


def test_refresh_failure_prints_the_corpus_warnings(tmp_path, monkeypatch):
    w = _warn_then_fail_world(tmp_path, monkeypatch)
    (res,) = refresh.refresh(w.entity, campaign="corp", runner=w.runner)
    assert res.failed
    assert any("--skips-json" in ln for ln in res.warnings()), res.warnings()


def test_failed_first_mine_reports_the_corpus_warnings_in_bringup(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch, authority=False)
    monkeypatch.setenv("MNEME_STUB_SKIPS_OUT", "missing")
    monkeypatch.setenv("MNEME_STUB_MINE_SKIPS_JSON", "[]")
    # `docs/npcs` mines (warning: no usable list); the later `grounding` kind then fails
    real = w.runner.runner

    def run(cmd):
        if "--wing" in cmd and cmd[cmd.index("--wing") + 1] == "grounding":
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom")
        return real(cmd)

    monkeypatch.setattr(w.runner, "runner", run)
    report = bringup.bringup(
        w.entity, "corp", runner=w.runner, config_json=tmp_path / "config.json", do_backup=False
    )
    assert not report.ready
    assert any("--skips-json" in ln for ln in report.warnings), report.warnings


def test_regenerate_failure_prints_the_corpus_warnings(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from mneme.cli import app
    from mneme.mempalace.runner import MempalaceRunner

    w = corpus_world(tmp_path, monkeypatch)
    _render_and_refresh(w)
    monkeypatch.setenv("MNEME_STUB_SKIPS_OUT", "missing")
    real = w.runner.runner

    def run(cmd):  # `npcs` mines (no usable skip list: a warning); `grounding` then fails
        if "--wing" in cmd and cmd[cmd.index("--wing") + 1] == "grounding":
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom")
        return real(cmd)

    monkeypatch.setattr(w.runner, "runner", run)
    monkeypatch.setattr(
        MempalaceRunner, "for_entity", classmethod(lambda cls, entity, **kw: w.runner)
    )
    monkeypatch.setattr("mneme.mempalace.cli._load_or_exit", lambda _c: w.entity)
    r = CliRunner().invoke(app, ["mp", "regenerate", "corp", "--confirm"])
    assert r.exit_code != 0
    assert "--skips-json" in r.output and "FAIL regenerate" in r.output, r.output
