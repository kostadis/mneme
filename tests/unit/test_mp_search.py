"""`mneme mp search` — search a campaign palace with the declared embedder (GH #73)."""

from __future__ import annotations

import dataclasses
import subprocess

import pytest
from typer.testing import CliRunner

from mneme.mempalace import authority, backup, bringup, cli
from mneme.mempalace.runner import MempalaceRunner
from tests.fixtures import STUB, entity_for, make_greenfield_campaign

EMBED_ENV = {
    "MEMPALACE_BACKEND": "turbovec",
    "MEMPALACE_EMBEDDING_PROVIDER": "ollama",
    "MEMPALACE_EMBEDDING_MODEL": "qwen3-embedding",
}


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("MNEME_STUB_LOG", str(tmp_path / "stub.log"))
    monkeypatch.setenv("MNEME_STUB_APPLY_STATE", str(tmp_path / "applied"))
    root = tmp_path / "campaigns"
    make_greenfield_campaign(root, "stormhaven")
    entity = dataclasses.replace(entity_for(root), env=dict(EMBED_ENV))
    bringup.bringup(entity, "stormhaven", runner=MempalaceRunner(binary=str(STUB)), do_backup=False)
    cmds: list[list[str]] = []
    rc = {"code": 0}

    def fake(cmd):
        cmds.append(cmd)
        return subprocess.CompletedProcess(cmd, rc["code"], stdout="", stderr="")

    seen_env: dict = {}

    def for_entity(cls, e, runner=None, *, stream=False):
        seen_env["env"] = dict(e.env)
        seen_env["stream"] = stream
        return MempalaceRunner("mempalace", fake, e.env)

    monkeypatch.setattr(cli, "_load_or_exit", lambda config: entity)
    monkeypatch.setattr(MempalaceRunner, "for_entity", classmethod(for_entity))
    return entity, cmds, rc, seen_env


def _search(*args):
    return CliRunner().invoke(cli.app, ["search", *args])


def test_argv_has_global_palace_before_search_and_flags(world):
    entity, cmds, _rc, seen = world
    res = _search(
        "stormhaven", "who is calmer", "--wing", "canon", "--room", "r1",
        "--results", "3", "--since", "2024-01-01", "--before", "2025-01-01",
    )
    assert res.exit_code == 0, res.output
    store = backup._store_path(entity, "stormhaven")
    assert cmds == [[
        "mempalace", "--palace", str(store), "search", "who is calmer",
        "--wing", "canon", "--room", "r1", "--results", "3",
        "--since", "2024-01-01", "--before", "2025-01-01",
    ]]
    assert seen["stream"] is True
    assert seen["env"]["MEMPALACE_EMBEDDING_PROVIDER"] == "ollama"


def test_absent_flags_omitted(world):
    _e, cmds, _rc, _s = world
    assert _search("stormhaven", "q").exit_code == 0
    assert cmds[0][3:] == ["search", "q"]
    assert cmds[0][1] == "--palace"


def test_nonzero_exit_propagated(world):
    _e, _cmds, rc, _s = world
    rc["code"] = 3
    assert _search("stormhaven", "q").exit_code == 3


def test_missing_embedder_refused_before_running(world, monkeypatch):
    entity, cmds, _rc, _s = world
    bare = dataclasses.replace(entity, env={"MEMPALACE_BACKEND": "turbovec"})
    monkeypatch.setattr(cli, "_load_or_exit", lambda config: bare)
    res = _search("stormhaven", "q")
    assert res.exit_code == cli.EXIT_RUNTIME
    assert "FAIL search" in res.output and "MEMPALACE_EMBEDDING_" in res.output
    assert cmds == []


def test_unknown_campaign_errors(world):
    _e, cmds, _rc, _s = world
    res = _search("nope", "q")
    assert res.exit_code == cli.EXIT_RUNTIME
    assert "FAIL search" in res.output
    assert cmds == []


def test_no_authority_errors(world, monkeypatch):
    _e, cmds, _rc, _s = world

    def boom(*a, **k):
        raise authority.AuthorityError(["no store pointer"])

    monkeypatch.setattr(backup, "_store_path", boom)
    res = _search("stormhaven", "q")
    assert res.exit_code == cli.EXIT_RUNTIME and "no store pointer" in res.output
    assert cmds == []
