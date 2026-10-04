"""GH #46 — hypostasis-declared env reaches every `mempalace` subprocess (Principle V)."""

from __future__ import annotations

import dataclasses
import subprocess

from mneme.mempalace import bringup, refresh
from mneme.mempalace.runner import MempalaceRunner
from tests.fixtures import entity_for, make_greenfield_campaign


def _capture(monkeypatch):
    seen: list[dict] = []

    def fake_run(cmd, **kw):
        seen.append({"cmd": cmd, **kw})
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    return seen


def _entity(tmp_path):
    e = entity_for(tmp_path / "campaigns")
    return dataclasses.replace(e, env={"MEMPALACE_BACKEND": "turbovec", "EXTRA": "1"})


def test_default_runner_overlay_wins_over_ambient(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMPALACE_BACKEND", "chroma")
    seen = _capture(monkeypatch)
    runner = MempalaceRunner.for_entity(_entity(tmp_path))
    assert runner.env["MEMPALACE_BACKEND"] == "turbovec"
    runner.status(tmp_path / "p")
    runner.is_stale(tmp_path)
    assert len(seen) == 2
    for call in seen:
        assert call["env"]["MEMPALACE_BACKEND"] == "turbovec"
        assert call["env"]["EXTRA"] == "1"
        assert call["env"]["PATH"]  # ambient still inherited


def test_stream_runner_gets_overlay_and_unbuffered(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMPALACE_BACKEND", "chroma")
    seen = _capture(monkeypatch)
    MempalaceRunner.for_entity(_entity(tmp_path), stream=True).mine(tmp_path)
    assert seen[0]["env"]["MEMPALACE_BACKEND"] == "turbovec"
    assert seen[0]["env"]["PYTHONUNBUFFERED"] == "1"


def test_no_env_is_plain_ambient(monkeypatch):
    monkeypatch.setenv("MEMPALACE_BACKEND", "chroma")
    seen = _capture(monkeypatch)
    MempalaceRunner.for_venv(None).status(None)
    assert seen[0]["env"]["MEMPALACE_BACKEND"] == "chroma"


def test_injected_runner_still_called_with_cmd_only():
    calls = []

    def fake(cmd):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    MempalaceRunner.for_venv(None, fake, env={"A": "b"}).status(None)
    assert len(calls) == 1


def test_bringup_and_refresh_build_env_runner(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("MEMPALACE_BACKEND", "chroma")
    root = tmp_path / "campaigns"
    make_greenfield_campaign(root, "stormhaven")
    entity = _entity(tmp_path)
    seen = _capture(monkeypatch)
    bringup.bringup(entity, "stormhaven", do_backup=False)
    mines = [c for c in seen if "mine" in c["cmd"]]
    assert mines and all(c["env"]["MEMPALACE_BACKEND"] == "turbovec" for c in mines)
    seen.clear()
    refresh.refresh(entity, "stormhaven")
    assert seen and all(c["env"]["MEMPALACE_BACKEND"] == "turbovec" for c in seen)


def test_migrate_verification_carries_entity_env(tmp_path, monkeypatch):
    """`mneme mp migrate` → migrate_in_dir → verify → check_dir: sync runs under entity.env."""
    from mneme.mempalace import migrate
    from mneme.mempalace.models import MigrationPlan, MigrationStep

    monkeypatch.setenv("MEMPALACE_BACKEND", "chroma")
    seen = _capture(monkeypatch)
    saga = tmp_path / "saga"
    saga.mkdir()
    auth = (
        'campaign: saga\nrecipe_version: "1.0.0"\nwings:\n'
        '  - {name: saga, source: ".", trust: reference, rooms: []}\n'
    )
    plan = MigrationPlan(
        campaign="saga",
        approved_by_human=True,
        steps=(MigrationStep("write_authority", {"content": auth}),),
    )
    runner = MempalaceRunner.for_entity(_entity(tmp_path))
    migrate.migrate_in_dir(plan, saga, runner=runner)
    syncs = [c for c in seen if "sync" in c["cmd"]]
    assert syncs and all(c["env"]["MEMPALACE_BACKEND"] == "turbovec" for c in syncs)


def test_migrate_cli_passes_entity_runner(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace

    from typer.testing import CliRunner

    from mneme.mempalace import cli, migrate, publish

    entity = _entity(tmp_path)
    monkeypatch.setattr(cli, "_load_or_exit", lambda config: entity)
    monkeypatch.setattr(publish, "_clone_workcopy", lambda *a: SimpleNamespace(path=tmp_path))
    got = {}

    def fake(plan, cdir, *, runner=None):
        got["runner"] = runner
        return migrate.MigrationResult(campaign="saga", conformant=True, note="ok")

    monkeypatch.setattr(migrate, "migrate_in_dir", fake)
    pf = tmp_path / "plan.json"
    pf.write_text(json.dumps({"campaign": "saga", "approved_by_human": True,
                              "steps": [{"op": "reindex", "args": {"wing": "saga"}}]}))
    res = CliRunner().invoke(cli.app, ["migrate", "saga", "--plan", str(pf)])
    assert res.exit_code == 0, res.output
    assert got["runner"].env["MEMPALACE_BACKEND"] == "turbovec"
