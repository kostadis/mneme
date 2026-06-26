"""US1 integration (T010): end-to-end bring-up via the stub binary — faces, store,
Brick Test (SC-007), isolation (SC-005), creation-time direct write (FR-005)."""

from __future__ import annotations

import json

import yaml

from mneme.mempalace import bringup
from mneme.mempalace.runner import MempalaceRunner
from tests.fixtures import STUB, entity_for, make_greenfield_campaign


def _stub_runner(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("MNEME_STUB_LOG", str(tmp_path / "stub.log"))
    return MempalaceRunner(binary=str(STUB))


def test_bringup_end_to_end(tmp_path, monkeypatch):
    runner = _stub_runner(tmp_path, monkeypatch)
    root = tmp_path / "campaigns"
    camp = make_greenfield_campaign(root, "stormhaven")
    report = bringup.bringup(entity_for(root), "stormhaven", runner=runner, do_backup=False)
    assert report.ready

    # four faces written (FR-002a)
    assert "palace: stormhaven" in (camp / "mempalace.yaml").read_text()  # cli_pointer (root wing)
    cg = yaml.safe_load((camp / "config.yaml").read_text())["mempalace"]  # cg_search face
    assert cg["canon_wing"]
    cj = json.loads((tmp_path / "home" / ".mempalace" / "config.json").read_text())  # global alias
    assert "stormhaven" in cj["palaces"]
    mcp = json.loads((camp / ".mcp.json").read_text())  # mcp face, palace injected (no hardcode)
    env = mcp["mcpServers"]["mempalace"]["env"]
    assert env["MEMPALACE_PALACE_PATH"].endswith("/palaces/stormhaven")

    # the dedicated turbovec store was created by the first mine
    store = tmp_path / "home" / ".mempalace" / "palaces" / "stormhaven"
    assert (store / "turbovec" / "mempalace_drawers" / "store.sqlite3").exists()


def test_brick_test_rebringup_reproduces(tmp_path, monkeypatch):
    runner = _stub_runner(tmp_path, monkeypatch)
    root = tmp_path / "campaigns"
    make_greenfield_campaign(root, "stormhaven")
    bringup.bringup(entity_for(root), "stormhaven", runner=runner, do_backup=False)
    store = tmp_path / "home" / ".mempalace" / "palaces" / "stormhaven"
    import shutil

    shutil.rmtree(store)  # delete the derived store entirely (SC-007)
    report = bringup.bringup(entity_for(root), "stormhaven", runner=runner, do_backup=False)
    assert report.ready
    assert (store / "turbovec" / "mempalace_drawers" / "store.sqlite3").exists()


def test_isolation_sibling_untouched(tmp_path, monkeypatch):
    runner = _stub_runner(tmp_path, monkeypatch)
    root = tmp_path / "campaigns"
    make_greenfield_campaign(root, "stormhaven")
    sibling = make_greenfield_campaign(root, "other")
    before = sorted(p.name for p in sibling.iterdir())
    bringup.bringup(entity_for(root), "stormhaven", runner=runner, do_backup=False)
    # the sibling campaign is untouched (SC-005): no .mneme, no new files
    assert sorted(p.name for p in sibling.iterdir()) == before
    cj = json.loads((tmp_path / "home" / ".mempalace" / "config.json").read_text())
    assert "other" not in cj["palaces"]  # only the brought-up campaign registered
