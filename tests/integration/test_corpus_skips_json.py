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
