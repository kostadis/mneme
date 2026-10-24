"""Runner methods for the 007 corpus verbs, against the recording stub."""

from __future__ import annotations

import json
import sys

import pytest

from mneme.mempalace.runner import ListedSkip, MempalaceError, MempalaceRunner, SourceRecord
from tests.fixtures import STUB


@pytest.fixture
def stub(tmp_path, monkeypatch):
    monkeypatch.setenv("MNEME_STUB_LOG", str(tmp_path / "log"))
    monkeypatch.setenv("MNEME_STUB_SOURCES_STATE", str(tmp_path / "state.json"))
    import subprocess

    def run(cmd):
        return subprocess.run([sys.executable, str(STUB), *cmd[1:]], capture_output=True, text=True)

    runner = MempalaceRunner("mempalace", run)
    camp = tmp_path / "camp"
    (camp / "docs").mkdir(parents=True)
    (camp / "docs" / "a.md").write_text("a\n")
    (camp / "docs" / "b.md").write_text("b\n")
    return runner, camp, tmp_path


def _log(tmp_path):
    return (tmp_path / "log").read_text().splitlines()


def test_mine_files_then_sources(stub):
    runner, camp, tmp = stub
    res = runner.mine_files(camp, ["docs/a.md", camp / "docs" / "b.md"], "npcs", tmp / "p")
    assert res == []
    line = _log(tmp)[0]
    assert "--palace" in line and "--files-from" in line and "--wing npcs" in line
    assert "--skips-json" in line
    got = runner.sources(tmp / "p")
    assert got is not None
    assert {(r.wing, r.source_file.rsplit("/", 1)[1], r.drawers) for r in got} == {
        ("npcs", "a.md", 1), ("npcs", "b.md", 1)
    }
    assert all(isinstance(r, SourceRecord) and r.source_mtime for r in got)
    assert [r.wing for r in runner.sources(tmp / "p", wing="other")] == []


def test_mine_files_dry_run_mines_nothing(stub):
    runner, camp, tmp = stub
    runner.mine_files(camp, ["docs/a.md"], "npcs", dry_run=True)
    assert "--dry-run" in _log(tmp)[0]
    assert runner.sources() == []


def test_mine_files_reports_skips(stub):
    runner, camp, tmp = stub
    res = runner.mine_files(camp, ["docs/nope.md"], "npcs")
    assert res == [ListedSkip("docs/nope.md", "not_regular", "not a regular file")]


def test_mine_files_skips_come_from_the_json_not_the_text(stub, monkeypatch):
    runner, camp, _ = stub
    monkeypatch.setenv("MNEME_STUB_MINE_SKIPS", "  SKIP: docs/a.md (missing)")
    monkeypatch.setenv(
        "MNEME_STUB_MINE_SKIPS_JSON",
        '[{"path": "docs/b.md", "reason": "too_large", "detail": "9 MB"}]',
    )
    assert runner.mine_files(camp, ["docs/a.md", "docs/b.md"], "npcs") == [
        ListedSkip("docs/b.md", "too_large", "9 MB")
    ]


@pytest.mark.parametrize("mode", ["missing", "garbled"])
def test_mine_files_unknown_when_skips_json_missing_or_garbled(stub, monkeypatch, mode):
    runner, camp, _ = stub
    monkeypatch.setenv("MNEME_STUB_SKIPS_OUT", mode)
    assert runner.mine_files(camp, ["docs/a.md"], "npcs") is None


def test_mine_files_unknown_when_skips_json_has_the_wrong_shape(stub, monkeypatch):
    runner, camp, _ = stub
    monkeypatch.setenv("MNEME_STUB_MINE_SKIPS_JSON", '[{"nope": 1}]')
    assert runner.mine_files(camp, ["docs/a.md"], "npcs") is None


def test_sources_unknown_on_rc1_and_garbage(stub, monkeypatch):
    runner, _, _ = stub
    monkeypatch.setenv("MNEME_STUB_SOURCES", "rc1")
    assert runner.sources() is None
    monkeypatch.setenv("MNEME_STUB_SOURCES", "garbage")
    assert runner.sources() is None


def test_sources_unknown_on_missing_binary():
    assert MempalaceRunner("/nonexistent/mempalace").sources() is None


def test_sources_unknown_on_wrong_shape(stub, tmp_path):
    runner, _, tmp = stub
    (tmp / "state.json").write_text(json.dumps([{"wing": "x"}]))
    assert runner.sources() is None


def test_forget_dry_run_then_apply(stub):
    runner, camp, tmp = stub
    runner.mine_files(camp, ["docs/a.md", "docs/b.md"], "npcs")
    a = camp / "docs" / "a.md"
    rep = runner.forget([a], apply=False)
    assert (rep.sources, rep.drawers) == (1, 1)
    assert rep.paths == (str(a.resolve()),)
    assert "--apply" not in _log(tmp)[-1]
    assert len(runner.sources()) == 2  # dry run deletes nothing
    runner.forget([a], apply=True)
    assert [r.source_file for r in runner.sources()] == [str((camp / "docs" / "b.md").resolve())]


def test_forget_apply_failure_raises(stub, monkeypatch):
    runner, camp, _ = stub
    monkeypatch.setenv("MNEME_STUB_FORGET", "rc1")
    with pytest.raises(MempalaceError):
        runner.forget([camp / "docs" / "a.md"], apply=True)


def test_forget_unparseable_report_raises(tmp_path):
    import subprocess

    def run(cmd):
        return subprocess.CompletedProcess(cmd, 0, stdout="done\n", stderr="")

    with pytest.raises(MempalaceError):
        MempalaceRunner("mempalace", run).forget(["x"], apply=True)


def test_supports_corpus(stub, monkeypatch):
    runner, _, tmp = stub
    assert runner.supports_corpus() is True
    runner.supports_corpus()
    assert sum("--help" in ln for ln in _log(tmp)) == 2  # probed once (top + mine), then cached
    monkeypatch.setenv("MNEME_STUB_OLD", "1")
    import subprocess

    def run(cmd):
        return subprocess.run([sys.executable, str(STUB), *cmd[1:]], capture_output=True, text=True)

    old = MempalaceRunner("mempalace", run)
    assert old.supports_corpus() is False
    assert "`mine --files-from`" in old.too_old_message()


def test_supports_corpus_false_when_help_lacks_skips_json(stub, monkeypatch):
    import subprocess

    runner, _, _ = stub
    monkeypatch.setenv("MNEME_STUB_OLD", "skips")

    def run(cmd):
        return subprocess.run([sys.executable, str(STUB), *cmd[1:]], capture_output=True, text=True)

    r = MempalaceRunner("mempalace", run)
    assert r.supports_corpus() is False
    assert r.corpus_gaps() == ["`mine --skips-json`"]
    assert "mine --skips-json" in r.too_old_message()


def test_probe_failure_raises_and_is_not_cached():
    import subprocess

    calls = []

    def run(cmd):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="Traceback: boom")

    r = MempalaceRunner("mempalace", run)
    with pytest.raises(MempalaceError, match="cannot probe mempalace capabilities.*boom"):
        r.supports_corpus()
    with pytest.raises(MempalaceError):
        r.supports_corpus_read()
    assert len(calls) == 2  # nothing cached from a failed probe


def test_supports_corpus_binary_missing_cannot_probe():
    with pytest.raises(MempalaceError, match="cannot probe"):
        MempalaceRunner("/nonexistent/mempalace").supports_corpus()


def test_read_capability_is_separate_from_mining(stub, monkeypatch):
    import subprocess

    _, _, _ = stub
    monkeypatch.setenv("MNEME_STUB_OLD", "skips")

    def run(cmd):
        return subprocess.run([sys.executable, str(STUB), *cmd[1:]], capture_output=True, text=True)

    r = MempalaceRunner("mempalace", run)
    assert r.supports_corpus_read() is True and r.supports_corpus() is False
