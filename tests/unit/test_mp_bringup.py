"""US1 unit tests (T009): bring-up sequence, dry-run, idempotency, not-ready-on-fail."""

from __future__ import annotations

import subprocess

from mneme.mempalace import authority, bringup
from mneme.mempalace.runner import MempalaceRunner
from tests.fixtures import entity_for, make_greenfield_campaign


def fake_runner(rc: int = 0):
    calls: list[list[str]] = []

    def run(cmd):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, rc, stdout="", stderr="boom" if rc else "")

    run.calls = calls
    return MempalaceRunner(binary="mempalace", runner=run)


def _setup(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    root = tmp_path / "campaigns"
    make_greenfield_campaign(root, "stormhaven")
    return entity_for(root), root


def test_bringup_steps_in_order_and_ready(tmp_path, monkeypatch):
    entity, root = _setup(tmp_path, monkeypatch)
    report = bringup.bringup(entity, "stormhaven", runner=fake_runner(), do_backup=False)
    assert report.ready and report.exit_code() == 0
    assert [s.name for s in report.steps] == [
        "configure", "render_faces", "provision", "first_mine", "backup"
    ]
    # creation-time direct write: the authority lives in the campaign workspace (FR-005)
    cfg = authority.load(root / "stormhaven")
    assert cfg.store is not None and cfg.store.alias == "stormhaven"


def test_bringup_dry_run_writes_nothing(tmp_path, monkeypatch):
    entity, root = _setup(tmp_path, monkeypatch)
    report = bringup.bringup(entity, "stormhaven", runner=fake_runner(), dry_run=True)
    assert all(s.state == "skipped" for s in report.steps)
    assert not authority.has_authority(root / "stormhaven")  # nothing written


def test_bringup_idempotent_rerun(tmp_path, monkeypatch):
    entity, root = _setup(tmp_path, monkeypatch)
    bringup.bringup(entity, "stormhaven", runner=fake_runner(), do_backup=False)
    again = bringup.bringup(entity, "stormhaven", runner=fake_runner(), do_backup=False)
    assert again.ready  # no duplicate/clobber, still ready


def test_bringup_failed_mine_is_not_ready(tmp_path, monkeypatch):
    entity, root = _setup(tmp_path, monkeypatch)
    report = bringup.bringup(entity, "stormhaven", runner=fake_runner(rc=1), do_backup=False)
    assert not report.ready and report.exit_code() == 1
    assert any(s.name == "first_mine" and s.state == "failed" for s in report.steps)
