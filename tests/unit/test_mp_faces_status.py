"""008 US3: the `faces` status row checks .mcp.json against the OWNING mneme binding."""

from __future__ import annotations

import dataclasses
import json
import subprocess

from mneme.mempalace import bringup, conform
from mneme.mempalace.models import State
from mneme.mempalace.runner import MempalaceRunner
from tests.fixtures import add_store_pointer, entity_for, make_campaigns


def _runner():
    def run(cmd):
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    return MempalaceRunner(binary="mempalace", runner=run)


def _faces(entity, name="full"):
    rep = conform.report(entity, campaign=name, runner=_runner())
    rows = [r for r in rep.for_campaign(name) if r.dimension == "faces"]
    assert len(rows) == 1
    return rows[0]


def _setup(tmp_path, *, store=True):
    root = make_campaigns(tmp_path / "campaigns")
    if store:
        add_store_pointer(root)
    entity = entity_for(root, mempalace=tmp_path / "mp")
    return root / "full", entity


def _edit(camp, fn):
    p = camp / ".mcp.json"
    d = json.loads(p.read_text())
    fn(d["mcpServers"])
    p.write_text(json.dumps(d))


def test_fresh_render_is_conformant(tmp_path):
    camp, entity = _setup(tmp_path)
    bringup.render_existing_faces(entity, "full")
    row = _faces(entity)
    assert row.state is State.CONFORMANT and row.note == "right store everywhere"


def test_missing_mneme_key_is_stale_and_rerender_fixes_it(tmp_path):
    camp, entity = _setup(tmp_path)
    bringup.render_existing_faces(entity, "full")
    _edit(camp, lambda s: s.pop("mneme"))
    row = _faces(entity)
    assert row.state is State.STALE_RENDER
    assert "has no mneme server" in row.note and "mneme mp faces full" in row.note
    bringup.render_existing_faces(entity, "full")
    assert _faces(entity).state is State.CONFORMANT


def test_bare_mempalace_command_is_flagged(tmp_path):
    camp, entity = _setup(tmp_path)
    bringup.render_existing_faces(entity, "full")
    _edit(camp, lambda s: s["mempalace"].update(command="mempalace-mcp"))
    row = _faces(entity)
    assert row.state is State.STALE_RENDER and "mempalace command !=" in row.note


def test_changed_config_arg_is_flagged(tmp_path):
    camp, entity = _setup(tmp_path)
    bringup.render_existing_faces(entity, "full")
    _edit(camp, lambda s: s["mneme"].update(args=["mp", "mcp", "--config", "/elsewhere.yaml"]))
    assert "mneme config !=" in _faces(entity).note


def test_invalid_json_is_unreadable(tmp_path):
    camp, entity = _setup(tmp_path)
    bringup.render_existing_faces(entity, "full")
    (camp / ".mcp.json").write_text("{not json")
    row = _faces(entity)
    assert row.state is State.STALE_RENDER and "unreadable" in row.note


def test_no_store_campaign_still_has_a_faces_row(tmp_path):
    camp, entity = _setup(tmp_path, store=False)
    assert "has no mneme server" in _faces(entity).note or "missing" in _faces(entity).note
    bringup.render_existing_faces(entity, "full")
    row = _faces(entity)
    assert row.state is State.CONFORMANT and row.note == "mneme server bound"


def test_venv_without_mneme_cannot_bind(tmp_path):
    camp, entity = _setup(tmp_path)
    bringup.render_existing_faces(entity, "full")
    (entity.venv / "bin" / "mneme").unlink()
    broken = dataclasses.replace(entity)
    row = _faces(broken)
    assert row.state is State.STALE_RENDER and "cannot bind owning mneme" in row.note
    assert "fix the mneme install" in row.note and "run `mneme mp faces" in row.note
    assert "mneme program missing" in row.note.split(" — ")[0]


# ── clone row (008 US4) ───────────────────────────────────────────────────────────


def _clone_setup(tmp_path, shared=("gm-assistant", "scripts")):
    from tests.unit.test_mcpface import _clone_campaign, _clone_entity

    tree, camp = _clone_campaign(tmp_path)
    return tree, camp, _clone_entity(tree, shared=shared, mempalace=tmp_path / "mp")


def _dim(entity, dim, name="toee"):
    rep = conform.report(entity, campaign=name, runner=_runner())
    return rep, [r for r in rep.for_campaign(name) if r.dimension == dim]


def test_single_clone_row_conformant_and_root_staleness_named(tmp_path):
    tree, camp, entity = _clone_setup(tmp_path)
    bringup.render_existing_faces(entity, "toee")
    _, (clone,) = _dim(entity, "clone")
    assert clone.state is State.CONFORMANT and clone.note == f"single-campaign clone {tree}"
    assert _dim(entity, "faces")[1][0].state is State.CONFORMANT
    p = tree / ".mcp.json"
    d = json.loads(p.read_text())
    d["mcpServers"].pop("mneme")
    p.write_text(json.dumps(d))
    row = _dim(entity, "faces")[1][0]
    assert row.state is State.STALE_RENDER and "root .mcp.json has no mneme server" in row.note


def test_multi_clone_row_owed_and_faces_cli_skipped(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from mneme.mempalace import cli

    tree, camp, entity = _clone_setup(tmp_path)
    (tree / "other").mkdir()
    bringup.render_existing_faces(entity, "toee")
    _, (clone,) = _dim(entity, "clone")
    assert clone.state is State.CLONE_ROOT_OWED and "holds 2 campaigns" in clone.note
    assert clone.state not in conform.FAIL_STATES
    assert conform.format_row(clone).startswith("todo")
    assert not (tree / ".mcp.json").exists()
    layout = bringup.faces_layout(entity, "toee")
    assert layout.verdict == "MULTI"
    # the CLI prints the skipped line (config loading stubbed to our entity)
    monkeypatch.setattr(cli, "_load_or_exit", lambda config: entity)
    res = CliRunner().invoke(cli.app, ["faces", "toee"])
    assert res.exit_code == 0, res.output
    assert f"skipped {tree}/.mcp.json: {layout.reason}" in res.output


def test_conflict_row_fails(tmp_path):
    tree, camp, entity = _clone_setup(tmp_path)
    (tree / "other").mkdir()
    (tree / ".mcp.json").write_text(json.dumps({"mcpServers": {"mempalace": {}}}))
    rep, (clone,) = _dim(entity, "clone")
    assert clone.state in conform.FAIL_STATES
    assert clone.state is State.CLONE_ROOT_CONFLICT and "kostadis/campaigns#672" in clone.note
    assert rep.exit_code() != 0


def test_undeclared_clone_row_lists_children(tmp_path):
    tree, camp, entity = _clone_setup(tmp_path, shared=None)
    _, (clone,) = _dim(entity, "clone")
    assert clone.state is State.CLONE_ROOT_OWED
    assert clone.note.endswith("holds: gm-assistant, scripts, toee")


def test_fixture_tree_campaigns_get_owed_clone_row(tmp_path):
    camp, entity = _setup(tmp_path)  # a tree of many campaigns, no shared set declared
    bringup.render_existing_faces(entity, "full")
    _, rows = _dim(entity, "clone", "full")
    assert rows and rows[0].state is State.CLONE_ROOT_OWED
    assert not (camp.parent / ".mcp.json").exists()
