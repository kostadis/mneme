"""GH #85: the MCP `search` tool — `mneme mp search` parity, returned not streamed."""

from __future__ import annotations

import dataclasses
import shutil
import subprocess

import pytest

from mneme.mcp import server
from mneme.mempalace import authority, backup, bringup, embedder_guard
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
    proc = {"code": 0, "stdout": "Source: a.md\nhit text\n", "stderr": ""}
    seen: dict = {}

    def fake(cmd):
        cmds.append(cmd)
        return subprocess.CompletedProcess(cmd, proc["code"], stdout=proc["stdout"],
                                           stderr=proc["stderr"])

    def for_entity(cls, e, runner=None, *, stream=False):
        seen["stream"] = stream
        return MempalaceRunner("mempalace", fake, e.env)

    monkeypatch.setattr(MempalaceRunner, "for_entity", classmethod(for_entity))
    return entity, cmds, proc, seen, root


def test_returns_output_with_cli_argv(world):
    entity, cmds, _p, seen, _root = world
    res = server.search(entity, "stormhaven", "who is calmer", wing="canon", room="r1",
                        results=3, since="2024-01-01", before="2025-01-01")
    store = backup._store_path(entity, "stormhaven")
    assert res == {"campaign": "stormhaven", "store": str(store),
                   "output": "Source: a.md\nhit text\n"}
    assert cmds == [[
        "mempalace", "--palace", str(store), "search",
        "--wing", "canon", "--room", "r1", "--results", "3",
        "--since", "2024-01-01", "--before", "2025-01-01", "--", "who is calmer",
    ]]
    assert seen["stream"] is False  # captured and returned, not streamed to a terminal


def test_absent_filters_omitted_and_dash_query_safe(world):
    entity, cmds, *_ = world
    server.search(entity, "stormhaven", "-2 to hit")
    assert cmds[0][3:] == ["search", "--", "-2 to hit"]


def test_campaign_dir_bypasses_name_lookup(world):
    entity, cmds, _p, _s, root = world
    res = server.search(entity, "stormhaven", "q", campaign_dir=str(root / "stormhaven"))
    assert "output" in res and len(cmds) == 1


def test_nonzero_exit_is_an_error(world):
    entity, _c, proc, *_ = world
    proc.update(code=2, stdout="", stderr="")
    assert server.search(entity, "stormhaven", "q") == {"error": "mempalace exited 2"}
    proc.update(stderr="Traceback ... boom")
    assert server.search(entity, "stormhaven", "q") == {"error": "Traceback ... boom"}


def test_unlaunchable_binary_reports_reason(world, monkeypatch):
    entity, *_ = world

    def broken(cls, e, runner=None, *, stream=False):
        def boom(cmd):
            raise OSError("no such file")
        return MempalaceRunner("mempalace", boom, e.env)

    monkeypatch.setattr(MempalaceRunner, "for_entity", classmethod(broken))
    assert server.search(entity, "stormhaven", "q") == {
        "error": "cannot run mempalace: no such file"}


@pytest.mark.parametrize("query,results", [("   ", None), ("q", 0)])
def test_bad_arguments_refused_before_running(world, query, results):
    entity, cmds, *_ = world
    assert "error" in server.search(entity, "stormhaven", query, results=results)
    assert cmds == []


def test_missing_embedder_refused_before_running(world):
    entity, cmds, *_ = world
    bare = dataclasses.replace(entity, env={"MEMPALACE_BACKEND": "turbovec"})
    res = server.search(bare, "stormhaven", "q")
    assert "MEMPALACE_EMBEDDING_" in res["error"] and cmds == []


def test_embedder_mismatch_refused(world, monkeypatch):
    entity, cmds, *_ = world
    monkeypatch.setattr(embedder_guard, "check", lambda e, s, prober=None: embedder_guard.GuardResult(
        embedder_guard.GuardState.MISMATCH, "dim 1024 != 384"))
    res = server.search(entity, "stormhaven", "q")
    assert "dim 1024 != 384" in res["error"] and cmds == []


def test_missing_store_refused(world):
    entity, cmds, *_ = world
    shutil.rmtree(backup._store_path(entity, "stormhaven"), ignore_errors=True)
    res = server.search(entity, "stormhaven", "q")
    assert "mneme mp bringup" in res["error"] and cmds == []


def test_unknown_campaign_is_an_error(world):
    entity, cmds, *_ = world
    assert "error" in server.search(entity, "nope", "q") and cmds == []


def test_no_authority_is_an_error(world, monkeypatch):
    entity, cmds, *_ = world

    def boom(*a, **k):
        raise authority.AuthorityError(["no store pointer"])

    monkeypatch.setattr(backup, "_store_path", boom)
    assert server.search(entity, "stormhaven", "q") == {"error": "no store pointer"}
    assert cmds == []


def test_tool_registered_on_server(world):
    import asyncio
    pytest.importorskip("mcp")
    entity, *_ = world
    tools = asyncio.run(server.build_server(entity).list_tools())  # mcp 1.x or 2.x
    tool = next(t for t in tools if t.name == "search")
    schema = getattr(tool, "input_schema", None) or tool.inputSchema  # mcp 2.x / 1.x
    assert {"campaign", "query", "campaign_dir"} <= set(schema["properties"])
