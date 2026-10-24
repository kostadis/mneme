"""Code-review round 6 (007): degraded-runner status rows, skip-aware staleness, warnings that
survive a failed mine, and the store-path / temp-file helpers."""

from __future__ import annotations

import json
import re

import pytest

from mneme.corpus import toc as corpus_toc
from mneme.mempalace import authority, bringup, conform, corpus_record, refresh
from mneme.mempalace.models import State
from mneme.mempalace.runner import MempalaceError, MempalaceRunner
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

def _record_skip(w, rel, reason, target=None):
    rec = corpus_record.read(w.store)
    files = {k: dict(v) for k, v in rec.files.items()}
    files[rel]["skipped"] = reason
    if target is not None:
        files[rel]["target"] = target
    corpus_record.write(
        w.store, rec.campaign, rec.corpus_sha256, files, excludes_sha256=rec.excludes_sha256
    )


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


def _mtime_far_after_the_mine(w):
    import os
    import time

    later = time.time() + 30
    os.utime(w.camp / "mempalace.yaml", (later, later))


def _excluded_world(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    settle(w)
    _record_skip(w, "docs/npcs/a.md", "excluded")
    assert "excluded by a mempalace.yaml" in corpus_row(w).note
    return w


def test_excluded_skip_survives_a_render_or_touch_that_leaves_the_content_identical(
    tmp_path, monkeypatch
):
    w = _excluded_world(tmp_path, monkeypatch)
    p = w.camp / "mempalace.yaml"
    p.write_text(p.read_text())  # a re-render: same bytes, newer mtime
    _mtime_far_after_the_mine(w)
    assert "excluded by a mempalace.yaml" in corpus_row(w).note


def test_excluded_skip_stops_applying_once_the_exclude_rules_changed(tmp_path, monkeypatch):
    w = _excluded_world(tmp_path, monkeypatch)
    p = w.camp / "mempalace.yaml"
    p.write_text(p.read_text() + "exclude:\n  - nothing/**\n")  # the exclude pattern changed
    row = corpus_row(w)
    assert "excluded by a mempalace.yaml" not in row.note
    assert "mneme mp refresh corp" in row.note


def test_excluded_skip_stops_applying_when_the_changed_file_got_its_old_mtime_back(
    tmp_path, monkeypatch
):
    import os

    w = _excluded_world(tmp_path, monkeypatch)
    p = w.camp / "mempalace.yaml"
    st = p.stat()
    p.write_text(p.read_text() + "exclude:\n  - nothing/**\n")
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))  # e.g. `git checkout` restoring a time
    assert "excluded by a mempalace.yaml" not in corpus_row(w).note


def test_excluded_skip_in_a_record_without_an_exclude_hash_is_refresh_retryable(
    tmp_path, monkeypatch
):
    w = corpus_world(tmp_path, monkeypatch)
    settle(w)
    rec = corpus_record.read(w.store)
    files = {k: dict(v) for k, v in rec.files.items()}
    files["docs/npcs/a.md"]["skipped"] = "excluded"
    corpus_record.write(w.store, rec.campaign, rec.corpus_sha256, files)  # an older record
    row = corpus_row(w)
    assert "excluded by a mempalace.yaml" not in row.note
    assert "mneme mp refresh corp" in row.note


def test_a_malformed_exclude_hash_makes_the_corpus_record_unreadable(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    settle(w)
    path = w.store / corpus_record.FILENAME
    doc = json.loads(path.read_text())
    doc["excludes_sha256"] = 5
    path.write_text(json.dumps(doc))
    with pytest.raises(corpus_record.CorpusRecordError):
        corpus_record.read(w.store)


def test_recorded_skip_of_an_unmined_file_stops_applying_when_its_target_changed(
    tmp_path, monkeypatch
):
    w = corpus_world(tmp_path, monkeypatch)
    write(w.camp, "docs/npcs/tiny.md", "x")
    _skips_json(monkeypatch, ("docs/npcs/tiny.md", "too_short", ""))
    settle(w)
    note = corpus_row(w).note
    assert "too short to index" in note and "docs/npcs/tiny.md" in note
    rec = corpus_record.read(w.store)
    files = {k: dict(v) for k, v in rec.files.items()}
    files["docs/npcs/tiny.md"]["target"] = "docs/npcs/old-target.md"  # re-pointed link
    corpus_record.write(w.store, rec.campaign, rec.corpus_sha256, files)
    note = corpus_row(w).note
    assert "too short to index" not in note
    assert "docs/npcs/tiny.md changed since it was skipped as too_short; refresh to retry" in note
    assert "mneme mp refresh corp" in note


def test_recorded_skip_of_a_held_file_stops_applying_when_its_target_changed(
    tmp_path, monkeypatch
):
    w = corpus_world(tmp_path, monkeypatch)
    settle(w)
    _record_skip(w, "docs/npcs/a.md", "too_short", target="docs/npcs/old-target.md")
    note = corpus_row(w).note
    assert "too short to index" not in note and "mneme mp refresh corp" in note


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


@pytest.mark.parametrize("field,bad", [("sha256", 5), ("kind", ["k"]), ("target", 5),
                                       ("target", ["a.md"])])
def test_non_string_record_fields_make_the_record_unreadable(tmp_path, field, bad):
    entry = {"kind": "k", "sha256": "h", "target": "a.md", field: bad}
    doc = {"schema": 1, "campaign": "c", "mined_at": "t", "corpus_sha256": "s",
           "files": {"a.md": entry}}
    corpus_record.record_path(tmp_path).write_text(json.dumps(doc))
    with pytest.raises(corpus_record.CorpusRecordError):
        corpus_record.read(tmp_path)


def test_refresh_survives_a_record_with_a_non_string_target(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    settle(w)
    path = corpus_record.record_path(w.store)
    doc = json.loads(path.read_text())
    doc["files"]["docs/npcs/a.md"]["target"] = 5
    path.write_text(json.dumps(doc))
    (res,) = refresh.refresh(w.entity, campaign="corp", runner=w.runner)
    assert not res.failed, res.error
    assert any("treating every file as unrecorded" in x for x in res.warnings())


# -- S8 / S9 -------------------------------------------------------------------------------

def _stray_file_store(w):
    import shutil

    shutil.rmtree(w.store)
    w.store.write_text("not a directory")


def test_status_reports_a_stray_file_at_the_store_path_as_unknown(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    settle(w)
    _stray_file_store(w)
    r, _ = rows(w)
    want = f"store path is not a directory: {w.store}"
    assert r["store"].state is State.INDEX_UNVERIFIED and want in r["store"].note
    assert r["corpus"].state is State.CORPUS_UNKNOWN and want in r["corpus"].note
    assert "embedder" not in r


def _dangling_store(w):
    import shutil

    if w.store.is_dir():
        shutil.rmtree(w.store)
    else:
        w.store.unlink()
    w.store.symlink_to(w.store.parent / "gone")


def test_prune_names_why_the_post_delete_verification_could_not_read_sources(
    tmp_path, monkeypatch
):
    from mneme.mempalace import prune as prune_mod

    w = corpus_world(tmp_path, monkeypatch)
    settle(w)
    w.runner.mine_files(w.camp, ["docs/party_draft.md"], wing="root", palace=w.store)
    inner, applied = w.runner.runner, []

    def run(cmd):
        if "--apply" in cmd:
            applied.append(cmd)
        elif applied and "sources" in cmd[1:]:
            raise PermissionError("denied")
        return inner(cmd)

    w.runner.runner = run
    out: list[str] = []
    ok = prune_mod.prune(w.entity, "corp", runner=w.runner, emit=out.append, confirm=True,
                         expect=1, include_former_canon=("root",))
    assert not ok and any("cannot run mempalace" in ln and "denied" in ln for ln in out), out


def test_a_dangling_symlink_at_the_store_path_is_refused_by_status_current_and_prune(
    tmp_path, monkeypatch
):
    from typer.testing import CliRunner

    from mneme.corpus import cli as ccli
    from mneme.mempalace import prune as prune_mod

    w = corpus_world(tmp_path, monkeypatch)
    settle(w)
    _dangling_store(w)
    want = f"store path is a dangling symlink: {w.store}"
    r, _ = rows(w)
    assert r["store"].state is State.INDEX_UNVERIFIED and want in r["store"].note
    assert r["corpus"].state is State.CORPUS_UNKNOWN and want in r["corpus"].note
    assert "embedder" not in r
    monkeypatch.setattr("mneme.corpus.cli._load_or_exit", lambda _c: w.entity)
    monkeypatch.setattr(MempalaceRunner, "for_entity", classmethod(lambda c, e, **k: w.runner))
    res = CliRunner().invoke(ccli.app, ["current", "corp"])
    assert res.exit_code != 0 and want in res.output
    with pytest.raises(authority.AuthorityError, match="dangling symlink"):
        prune_mod.prune(w.entity, "corp", runner=w.runner, emit=lambda ln: None)


def test_bringup_refuses_a_dangling_symlink_at_the_store_path_before_writing_anything(
    tmp_path, monkeypatch
):
    from tests.fixtures.corpus_campaign import tree_snapshot

    w = corpus_world(tmp_path, monkeypatch, authority=False)
    w.store.parent.mkdir(parents=True)
    w.store.symlink_to(w.store.parent / "gone")
    before = tree_snapshot(w.camp)
    report = bringup.bringup(
        w.entity, "corp", runner=w.runner, config_json=tmp_path / "config.json", do_backup=False
    )
    assert not report.ready
    assert any("store path is a dangling symlink" in st.note for st in report.steps)
    assert tree_snapshot(w.camp) == before and w.store.is_symlink()


def test_regenerate_refuses_a_broken_store_path_and_touches_nothing(tmp_path, monkeypatch):
    from mneme.mempalace import backup

    w = corpus_world(tmp_path, monkeypatch)
    settle(w)
    _stray_file_store(w)
    w.log.write_text("")
    with pytest.raises(MempalaceError, match="store path is not a directory"):
        backup.regenerate(w.entity, "corp", runner=w.runner)
    assert w.store.read_text() == "not a directory" and w.log_lines() == []
    _dangling_store(w)
    with pytest.raises(MempalaceError, match="dangling symlink"):
        backup.regenerate(w.entity, "corp", runner=w.runner)
    assert w.store.is_symlink() and w.log_lines() == []


def test_refresh_refuses_a_broken_store_path_before_any_mempalace_call(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    settle(w)
    _stray_file_store(w)
    w.log.write_text("")
    (res,) = refresh.refresh(w.entity, campaign="corp", runner=w.runner)
    assert res.failed and f"store path is not a directory: {w.store}" in res.error
    _dangling_store(w)
    (res,) = refresh.refresh(w.entity, campaign="corp", runner=w.runner)
    assert res.failed and f"store path is a dangling symlink: {w.store}" in res.error
    assert w.log_lines() == []


def test_corpus_current_and_prune_refuse_a_stray_file_at_the_store_path(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from mneme.corpus import cli as ccli
    from mneme.mempalace import prune as prune_mod

    w = corpus_world(tmp_path, monkeypatch)
    settle(w)
    _stray_file_store(w)
    monkeypatch.setattr("mneme.corpus.cli._load_or_exit", lambda _c: w.entity)
    monkeypatch.setattr(MempalaceRunner, "for_entity", classmethod(lambda c, e, **k: w.runner))
    res = CliRunner().invoke(ccli.app, ["current", "corp"])
    assert res.exit_code != 0 and f"store path is not a directory: {w.store}" in res.output
    with pytest.raises(authority.AuthorityError, match="store path is not a directory"):
        prune_mod.prune(w.entity, "corp", runner=w.runner, emit=lambda ln: None)


def test_bringup_refuses_a_stray_file_at_the_store_path_before_writing_anything(
    tmp_path, monkeypatch
):
    from tests.fixtures.corpus_campaign import tree_snapshot

    w = corpus_world(tmp_path, monkeypatch, authority=False)
    w.store.parent.mkdir(parents=True)
    w.store.write_text("not a directory")
    before = tree_snapshot(w.camp)
    report = bringup.bringup(
        w.entity, "corp", runner=w.runner, config_json=tmp_path / "config.json", do_backup=False
    )
    assert not report.ready
    assert any("store path is not a directory" in st.note for st in report.steps)
    assert tree_snapshot(w.camp) == before and w.store.read_text() == "not a directory"
    assert not (tmp_path / "config.json").exists()


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


@pytest.mark.parametrize("name", [".mneme-lock.tmp", ".mneme-x.json.tmp", ".hidden.tmp",
                                  ".x.json.ab12.bak"])
def test_other_dotfiles_are_not_write_json_temp_files(tmp_path, name):
    from mneme import atomic

    assert not atomic.is_temp(name)
    (tmp_path / name).write_text("")
    from mneme.mempalace.runner import StoreKind, store_state

    assert store_state(tmp_path).kind is StoreKind.PRESENT


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


# -- launch failure has one shape ------------------------------------------------------------

def _unlaunchable(tmp_path, kind):
    """A runner whose binary is missing, or exists but is not executable."""
    from mneme.mempalace.runner import _run

    if kind == "missing":
        return MempalaceRunner(str(tmp_path / "no-such-mempalace"), _run)
    bad = tmp_path / "not-executable"
    bad.write_text("#!/bin/sh\n")
    bad.chmod(0o644)
    return MempalaceRunner(str(bad), _run)


def _status_shape(w, runner):
    rep = conform.report(w.entity, "corp", runner=runner)
    return {r.dimension: (r.state, "cannot run mempalace" in r.note) for r in rep.rows
            if r.dimension in ("store", "embedder", "backup", "faces", "corpus", "index")}


def test_missing_and_non_executable_binaries_give_the_same_status_rows(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    settle(w)
    missing = _status_shape(w, _unlaunchable(tmp_path, "missing"))
    non_exec = _status_shape(w, _unlaunchable(tmp_path, "non-exec"))
    assert missing == non_exec
    assert missing["store"] == (State.INDEX_UNVERIFIED, True)
    assert missing["corpus"] == (State.CORPUS_UNKNOWN, True)
    assert {"backup", "faces"} <= missing.keys()


@pytest.mark.parametrize("kind", ["missing", "non-exec"])
def test_prune_with_an_unlaunchable_binary_refuses_cleanly(tmp_path, monkeypatch, kind):
    from mneme.mempalace import prune

    w = corpus_world(tmp_path, monkeypatch)
    settle(w)
    runner = _unlaunchable(tmp_path, kind)
    runner._read_gaps = []  # capability already probed; the sources read is what cannot run
    with pytest.raises(MempalaceError, match="cannot read the palace's drawer sources: cannot run"):
        prune.prune(w.entity, "corp", runner=runner, emit=lambda ln: None)


@pytest.mark.parametrize("kind", ["missing", "non-exec"])
def test_refresh_with_an_unlaunchable_binary_fails_without_a_traceback(
    tmp_path, monkeypatch, kind
):
    w = corpus_world(tmp_path, monkeypatch)
    settle(w)
    runner = _unlaunchable(tmp_path, kind)
    (res,) = refresh.refresh(w.entity, campaign="corp", runner=runner)
    assert res.failed and "cannot" in res.error
