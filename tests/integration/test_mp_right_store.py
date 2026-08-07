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


# ── 006 — the same campaign on two hosts (US2) ──────────────────────────────────


def test_two_hosts_share_bytes_and_resolve_their_own_store(tmp_path, monkeypatch):
    """The GH #51 repro for the store half.

    One campaign checkout, two hosts with different palace roots. Before 006 the tracked
    authority carried an absolute path, so each host rewrote it to its own $HOME forever.
    """
    monkeypatch.setenv("MNEME_STUB_LOG", str(tmp_path / "stub.log"))
    runner = MempalaceRunner(binary=str(STUB))
    root = tmp_path / "campaigns"
    camp = make_greenfield_campaign(root, "stormhaven")
    mp_a, mp_b = tmp_path / "hostA" / ".mempalace", tmp_path / "hostB" / ".mempalace"

    bringup.bringup(entity_for(root, mempalace=mp_a), "stormhaven", runner=runner, do_backup=False)
    tracked = camp / ".mneme" / "mempalace.yaml"
    after_a = tracked.read_bytes()

    # The tracked authority names the alias and nothing host-local (FR-010).
    assert "path:" not in after_a.decode()
    assert str(mp_a) not in after_a.decode()

    # Host B renders the same campaign — and does NOT rewrite the tracked file (SC-002).
    bringup.render_existing_faces(entity_for(root, mempalace=mp_b), "stormhaven")
    assert tracked.read_bytes() == after_a

    # Each host resolves its own store from those identical bytes (SC-003).
    cfg_a = authority.load(camp, mempalace_root=mp_a)
    cfg_b = authority.load(camp, mempalace_root=mp_b)
    assert cfg_a.store.path == mp_a / "palaces" / "stormhaven"
    assert cfg_b.store.path == mp_b / "palaces" / "stormhaven"

    # FR-015 — "right store everywhere" still holds, now per host: B's faces name B's root.
    assert render.faces_coherent(cfg_b, camp, mp_b / "config.json") == []
    mcp = (camp / ".mcp.json").read_text()
    assert str(mp_b / "palaces" / "stormhaven") in mcp
    assert str(mp_a / "palaces" / "stormhaven") not in mcp


def test_status_reports_legacy_store_path_as_a_todo(tmp_path, monkeypatch):
    # FR-013 — a legacy path that agrees with the derived location is owed cleanup.
    import subprocess

    from mneme.mempalace import conform

    monkeypatch.setenv("MNEME_STUB_LOG", str(tmp_path / "stub.log"))
    runner = MempalaceRunner(binary=str(STUB))
    root = tmp_path / "campaigns"
    camp = make_greenfield_campaign(root, "stormhaven")
    mp = tmp_path / "mp"
    entity = entity_for(root, mempalace=mp)
    bringup.bringup(entity, "stormhaven", runner=runner, do_backup=False)

    tracked = camp / ".mneme" / "mempalace.yaml"
    derived = mp / "palaces" / "stormhaven"
    tracked.write_text(
        tracked.read_text().replace(
            "  alias: stormhaven", f"  alias: stormhaven\n  path: {derived}"
        )
    )

    def run(cmd):
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    report = conform.report(entity, runner=MempalaceRunner(binary="mempalace", runner=run))
    rows = {r.dimension: r for r in report.rows if r.campaign == "stormhaven"}
    assert "authority" in rows and "legacy store.path" in rows["authority"].note


def test_conflicting_legacy_path_is_one_bad_row_not_a_wedged_fleet(tmp_path, monkeypatch):
    # FR-014 / FR-014a — the campaign is unloadable, every OTHER campaign still reports.
    import subprocess

    from mneme.mempalace import conform

    monkeypatch.setenv("MNEME_STUB_LOG", str(tmp_path / "stub.log"))
    runner = MempalaceRunner(binary=str(STUB))
    root = tmp_path / "campaigns"
    broken = make_greenfield_campaign(root, "obelisk")
    make_greenfield_campaign(root, "toee")
    mp = tmp_path / "mp"
    entity = entity_for(root, mempalace=mp)
    for name in ("obelisk", "toee"):
        bringup.bringup(entity, name, runner=runner, do_backup=False)

    tracked = broken / ".mneme" / "mempalace.yaml"
    tracked.write_text(
        tracked.read_text().replace(
            "  alias: obelisk",
            "  alias: obelisk\n  path: /home/someone-else/.mempalace/palaces/obelisk",
        )
    )

    def run(cmd):
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    report = conform.report(entity, runner=MempalaceRunner(binary="mempalace", runner=run))
    obelisk = [r for r in report.rows if r.campaign == "obelisk"]
    toee = [r for r in report.rows if r.campaign == "toee"]
    assert any("someone-else" in (r.note or "") for r in obelisk)  # names both locations
    assert len(toee) > 1 and any(r.dimension == "render" for r in toee)  # unaffected
