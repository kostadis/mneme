"""Code-review round 6 (007): degraded-runner status rows, skip-aware staleness, warnings that
survive a failed mine, and the store-path / temp-file helpers."""

from __future__ import annotations

import json
import re

import pytest

from mneme.corpus import toc as corpus_toc
from mneme.mempalace import bringup, conform, corpus_record, refresh
from mneme.mempalace.models import State
from mneme.mempalace.runner import MempalaceError, MempalaceRunner, holds_no_palace
from tests.fixtures import STUB, entity_for, make_greenfield_campaign, with_onnx
from tests.fixtures.corpus_campaign import corpus_world, write
from tests.integration.test_corpus_mining import _declare, _render_and_refresh, _skips_json
from tests.integration.test_corpus_status_prune import corpus_row, rows, settle


def _cannot_launch(cmd):
    raise PermissionError("denied")


# -- S1 ------------------------------------------------------------------------------------

def test_unlaunchable_binary_still_reports_embedder_backup_and_faces_rows(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("MNEME_STUB_LOG", str(tmp_path / "stub.log"))
    root = tmp_path / "campaigns"
    make_greenfield_campaign(root, "stormhaven")
    entity = with_onnx(entity_for(root))
    bringup.bringup(entity, "stormhaven", runner=MempalaceRunner(binary=str(STUB)), do_backup=True)
    broken = MempalaceRunner(binary="mempalace", runner=_cannot_launch)
    report = conform.report(entity, "stormhaven", runner=broken)
    by_dim = {r.dimension: r for r in report.for_campaign("stormhaven")}
    assert by_dim["store"].state is State.INDEX_UNVERIFIED
    assert "unverified" in by_dim["store"].note and "denied" in by_dim["store"].note
    assert {"embedder", "backup", "faces"} <= by_dim.keys()
    assert by_dim["faces"].state is State.CONFORMANT


# -- S2 ------------------------------------------------------------------------------------

def test_sources_that_cannot_be_launched_make_the_corpus_and_index_rows_unknown(
    tmp_path, monkeypatch
):
    w = corpus_world(tmp_path, monkeypatch)
    settle(w)
    inner = w.runner.runner

    def run(cmd):
        if "sources" in cmd[1:]:
            raise PermissionError("denied")
        return inner(cmd)

    w.runner.runner = run
    r, _ = rows(w)
    assert r["corpus"].state is State.CORPUS_UNKNOWN and "denied" in r["corpus"].note
    assert r["index"].state is State.INDEX_UNVERIFIED


# -- S4 ------------------------------------------------------------------------------------

def _record_skip(w, rel, reason):
    rec = corpus_record.read(w.store)
    files = {k: dict(v) for k, v in rec.files.items()}
    files[rel]["skipped"] = reason
    corpus_record.write(w.store, rec.campaign, rec.corpus_sha256, files)


def test_held_file_whose_remine_was_skipped_is_stale_not_current(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    settle(w)
    _record_skip(w, "docs/npcs/a.md", "purge_skipped")
    row = corpus_row(w)
    assert row.state is State.CORPUS_STALE, row.note
    assert "docs/npcs/a.md" in row.note and "mneme mp refresh corp" in row.note


def test_held_file_skipped_for_a_reason_refresh_cannot_fix_names_that_remedy(
    tmp_path, monkeypatch
):
    w = corpus_world(tmp_path, monkeypatch)
    settle(w)
    _record_skip(w, "docs/npcs/a.md", "too_short")
    row = corpus_row(w)
    assert row.state is State.CORPUS_STALE, row.note
    assert "too short to index: add content" in row.note
    assert "mneme mp refresh corp" not in row.note


# -- S5 / S6 -------------------------------------------------------------------------------

def test_failed_kind_carries_an_earlier_kinds_record_warning(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    write(w.camp, "a/x.md", "one")
    write(w.camp, "b/y.md", "two")
    _declare(w, "campaign: corp\nkinds:\n  npcs:\n    dirs: [a]\n  summaries:\n    dirs: [b]\n")

    def full_disk(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(corpus_record, "merge_kind", full_disk)
    real = w.runner.mine_files

    def mine_files(camp, targets, *, wing, palace=None):
        if wing == "summaries":
            raise MempalaceError("summaries exploded")
        return real(camp, targets, wing=wing, palace=palace)

    monkeypatch.setattr(w.runner, "mine_files", mine_files)
    (res,) = _render_and_refresh(w)
    assert res.failed
    assert "disk full" in (res.record_warning or ""), res.warnings()


def test_invalid_corpus_reports_the_toc_write_warning(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    write(w.camp, "docs/a.md", "x")
    _declare(
        w, "campaign: corp\nkinds:\n  npcs:\n    dirs: [docs]\n  summaries:\n    dirs: [docs]\n"
    )

    def unwritable(*a, **k):
        raise OSError("read-only campaign dir")

    monkeypatch.setattr(corpus_toc, "write", unwritable)
    (res,) = refresh.refresh(w.entity, campaign="corp", runner=w.runner)
    assert res.failed and "invalid corpus" in res.error
    assert any("could not write the corpus TOC snapshot" in ln for ln in res.warnings())


# -- S7 ------------------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [["too_short"], {"a": 1}, 7])
def test_non_string_skipped_value_makes_the_record_unreadable(tmp_path, bad):
    doc = {"schema": 1, "campaign": "c", "mined_at": "t", "corpus_sha256": "s",
           "files": {"a.md": {"kind": "k", "sha256": "h", "target": "a.md", "skipped": bad}}}
    corpus_record.record_path(tmp_path).write_text(json.dumps(doc))
    with pytest.raises(corpus_record.CorpusRecordError):
        corpus_record.read(tmp_path)


# -- S8 / S9 -------------------------------------------------------------------------------

def test_a_regular_file_at_the_store_path_holds_no_palace(tmp_path):
    f = tmp_path / "store"
    f.write_text("not a directory")
    assert holds_no_palace(f)
    assert holds_no_palace(tmp_path / "missing")


def test_atomic_names_the_temp_files_write_json_leaves_behind(tmp_path, monkeypatch):
    from mneme import atomic

    seen = []

    def boom(src, dst):
        seen.append(src)
        raise OSError("interrupted")

    monkeypatch.setattr(atomic.os, "replace", boom)
    with pytest.raises(OSError):
        atomic.write_json(tmp_path / "mneme-x.json", {})
    # the temp file is removed on failure; its NAME is what is_temp recognises
    import pathlib

    assert atomic.is_temp(pathlib.Path(seen[0]).name)
    assert not atomic.is_temp("mneme-x.json")


# -- S10 -----------------------------------------------------------------------------------

def test_unmined_note_marks_each_truncated_remedy_group_and_the_refreshable_list(
    tmp_path, monkeypatch
):
    w = corpus_world(tmp_path, monkeypatch)
    _declare(w, "campaign: corp\nkinds:\n  summaries:\n    dirs: [cx]\n")
    write(w.camp, "cx/ok.md", "fine")
    tiny = [f"cx/t{i:02}.md" for i in range(12)]
    for p in tiny:
        write(w.camp, p, "x")
    _skips_json(monkeypatch, *((p, "too_short", "") for p in tiny))
    _render_and_refresh(w)
    for i in range(12):
        write(w.camp, f"cx/new{i:02}.md", "later")
    note = corpus_row(w).note
    short = re.search(r"too short to index[^\[]*\[([^\]]*)\]", note)
    fresh = re.search(r"mneme mp refresh corp \[([^\]]*)\]", note)
    assert short and "(+2 more)" in short.group(1), note
    assert fresh and "(+2 more)" in fresh.group(1), note
