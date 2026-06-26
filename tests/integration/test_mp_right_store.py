"""US5 integration (T022): right store everywhere — CLI pointer + MCP faces agree (SC-008);
a removed palace pointer is flagged."""

from __future__ import annotations

from mneme.mempalace import authority, bringup, render
from mneme.mempalace.runner import MempalaceRunner
from tests.fixtures import STUB, entity_for, make_greenfield_campaign


def _bring_up(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("MNEME_STUB_LOG", str(tmp_path / "stub.log"))
    runner = MempalaceRunner(binary=str(STUB))
    root = tmp_path / "campaigns"
    camp = make_greenfield_campaign(root, "stormhaven")
    bringup.bringup(entity_for(root), "stormhaven", runner=runner, do_backup=False)
    return camp


def test_faces_agree_on_the_store(tmp_path, monkeypatch):
    camp = _bring_up(tmp_path, monkeypatch)
    cfg = authority.load(camp)
    config_json = tmp_path / "home" / ".mempalace" / "config.json"
    assert render.faces_coherent(cfg, camp, config_json) == []  # CLI pointer + MCP agree


def test_removed_palace_pointer_is_flagged(tmp_path, monkeypatch):
    camp = _bring_up(tmp_path, monkeypatch)
    cfg = authority.load(camp)
    config_json = tmp_path / "home" / ".mempalace" / "config.json"
    # hand-break the cli_pointer face: rewrite the root mempalace.yaml without palace:
    (camp / "mempalace.yaml").write_text("wing: stormhaven\nrooms: []\n")
    mism = render.faces_coherent(cfg, camp, config_json)
    assert any("cli_pointer" in m for m in mism)  # the wrong/missing-pointer bug is caught
