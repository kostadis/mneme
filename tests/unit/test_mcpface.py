import json
import os
import stat
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from hypostasis.models import MnemeIdentity
from mneme.mempalace import bringup, discover, ownership, render
from mneme.mempalace.mcpface import (
    McpBindingError,
    McpFaceError,
    binding_for,
    mempalace_entry,
    merge_write,
    mneme_entry,
)
from mneme.mempalace.runner import MempalaceRunner
from tests.fixtures import (
    STUB,
    entity_for,
    entity_for_trees,
    fake_binding,
    make_greenfield_campaign,
    make_simple_campaign,
)

ID_A = MnemeIdentity(id="aaaaaaaa-0000-0000-0000-000000000000", label="fleet-a")
ID_B = MnemeIdentity(id="bbbbbbbb-0000-0000-0000-000000000000", label="fleet-b")


def _touch_exe(p):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.touch()
    p.chmod(0o755)


@pytest.fixture
def entity(tmp_path):
    _touch_exe(tmp_path / "venv" / "bin" / "mneme")
    _touch_exe(tmp_path / "venv" / "bin" / "mempalace-mcp")
    cfg = tmp_path / "hypostasis.yaml"
    cfg.write_text("x: 1\n")
    return SimpleNamespace(
        venv=tmp_path / "venv",
        env={"MEMPALACE_BACKEND": "turbovec", "OPENAI_API_KEY": "sk-secret"},
        source_path=cfg,
    )


def test_binding_paths_absolute(entity, tmp_path):
    b = binding_for(entity, need_mempalace=True)
    assert b.mneme_program == tmp_path / "venv" / "bin" / "mneme"
    assert b.mempalace_program == tmp_path / "venv" / "bin" / "mempalace-mcp"
    assert b.config_path == tmp_path / "hypostasis.yaml"
    assert all(p.is_absolute() for p in (b.mneme_program, b.mempalace_program, b.config_path))


def test_missing_programs_and_config(entity, tmp_path):
    (tmp_path / "venv" / "bin" / "mempalace-mcp").unlink()
    binding_for(entity, need_mempalace=False)
    with pytest.raises(McpBindingError, match="mempalace-mcp"):
        binding_for(entity, need_mempalace=True)
    (tmp_path / "venv" / "bin" / "mneme").unlink()
    with pytest.raises(McpBindingError, match="mneme program"):
        binding_for(entity, need_mempalace=False)
    entity.source_path = None
    with pytest.raises(McpBindingError) as ei:
        binding_for(entity, need_mempalace=True)
    msg = str(ei.value)
    assert "config path unknown" in msg and "mneme program" in msg and "mempalace-mcp" in msg


def test_path_decoy_ignored(entity, tmp_path, monkeypatch):
    _touch_exe(tmp_path / "decoy" / "mempalace-mcp")
    _touch_exe(tmp_path / "decoy" / "mneme")
    monkeypatch.setenv("PATH", f"{tmp_path / 'decoy'}:/usr/bin")
    b = binding_for(entity, need_mempalace=True)
    assert b.mempalace_program == tmp_path / "venv" / "bin" / "mempalace-mcp"
    assert b.mneme_program == tmp_path / "venv" / "bin" / "mneme"


def test_entries(entity, tmp_path):
    b = binding_for(entity, need_mempalace=True)
    me = mneme_entry(b)
    assert me == {
        "type": "stdio",
        "command": str(tmp_path / "venv" / "bin" / "mneme"),
        "args": ["mp", "mcp", "--config", str(tmp_path / "hypostasis.yaml")],
    }
    mp = mempalace_entry(b, "/store/p")
    assert mp == {
        "type": "stdio",
        "command": str(tmp_path / "venv" / "bin" / "mempalace-mcp"),
        "env": {"MEMPALACE_PALACE_PATH": "/store/p", "MEMPALACE_BACKEND": "turbovec"},
    }
    assert "sk-secret" not in json.dumps([me, mp])


def test_merge_write_creates(tmp_path):
    p = tmp_path / ".mcp.json"
    assert merge_write(p, {"mneme": {"a": 1}}) == p
    assert json.loads(p.read_text()) == {"mcpServers": {"mneme": {"a": 1}}}


def test_merge_write_preserves(tmp_path):
    p = tmp_path / ".mcp.json"
    p.write_text(
        json.dumps(
            {
                "other": 1,
                "mcpServers": {
                    "campaign": {"c": 1},
                    "5etools": {"d": 2},
                    "mempalace": {"old": True},
                },
            }
        )
    )
    merge_write(p, {"mempalace": {"new": True}, "mneme": {"m": 1}})
    data = json.loads(p.read_text())
    assert list(data["mcpServers"]) == ["campaign", "5etools", "mempalace", "mneme"]
    assert data["mcpServers"]["campaign"] == {"c": 1}
    assert data["mcpServers"]["5etools"] == {"d": 2}
    assert data["mcpServers"]["mempalace"] == {"new": True}
    assert data["other"] == 1
    assert [f.name for f in tmp_path.iterdir()] == [".mcp.json"]


@pytest.mark.parametrize("content", ["{not json", "[1, 2]", '{"mcpServers": []}'])
def test_merge_write_bad_file_untouched(tmp_path, content):
    p = tmp_path / ".mcp.json"
    p.write_text(content)
    with pytest.raises(McpFaceError) as ei:
        merge_write(p, {"mneme": {}})
    assert str(p) in str(ei.value)
    assert p.read_text() == content
    assert [f.name for f in tmp_path.iterdir()] == [".mcp.json"]


def test_merge_write_preserves_existing_mode(tmp_path):
    p = tmp_path / ".mcp.json"
    p.write_text("{}")
    p.chmod(0o644)
    merge_write(p, {"mneme": {"m": 1}})
    assert stat.S_IMODE(p.stat().st_mode) == 0o644


def test_merge_write_new_file_uses_umask_default(tmp_path):
    old = os.umask(0o022)
    try:
        p = tmp_path / ".mcp.json"
        merge_write(p, {"mneme": {"m": 1}})
    finally:
        os.umask(old)
    assert stat.S_IMODE(p.stat().st_mode) == 0o644


# ── render (T011/T012/T015/T017) ────────────────────────────────────────────────


def _snapshot(*roots):
    snap = {}
    for root in roots:
        root = Path(root)
        files = [root] if root.is_file() else sorted(q for q in root.rglob("*") if q.is_file())
        for q in files:
            snap[str(q)] = q.read_bytes()
    return snap


def _managed(tmp_path, monkeypatch, name="stormhaven", env=None):
    """A greenfield campaign brought up under the hermetic fake owner."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("MNEME_STUB_LOG", str(tmp_path / "stub.log"))
    root = tmp_path / "campaigns"
    camp = make_greenfield_campaign(root, name)
    entity = entity_for(root)
    if env:
        entity = replace(entity, env=env)
    return root, camp, entity, MempalaceRunner(binary=str(STUB))


def test_managed_render_binds_owning_mneme(tmp_path, monkeypatch):
    root, camp, entity, runner = _managed(tmp_path, monkeypatch, env=OWN_ENV)
    (camp / ".mcp.json").write_text(json.dumps({"mcpServers": {"campaign": {"type": "stdio"}}}))
    report = bringup.bringup(entity, "stormhaven", runner=runner, do_backup=False)
    assert report.ready
    servers = json.loads((camp / ".mcp.json").read_text())["mcpServers"]
    venv = tmp_path / ".fake-venv"
    assert servers["campaign"] == {"type": "stdio"}  # preserved unchanged
    assert servers["mneme"] == {
        "type": "stdio",
        "command": str(venv / "bin" / "mneme"),
        "args": ["mp", "mcp", "--config", str(tmp_path / "hypostasis.yaml")],
    }
    assert servers["mempalace"]["command"] == str(venv / "bin" / "mempalace-mcp")
    assert "OPENAI_API_KEY" not in (camp / ".mcp.json").read_text()
    assert "sk-secret" not in (camp / ".mcp.json").read_text()


OWN_ENV = {"MEMPALACE_BACKEND": "turbovec", "OPENAI_API_KEY": "sk-secret"}


def test_render_without_store_writes_mneme_only(tmp_path):
    camp = tmp_path / "c"
    camp.mkdir()
    (camp / ".mcp.json").write_text(json.dumps({"mcpServers": {"mempalace": {"keep": 1}}}))
    cfg = replace(_unstored_cfg(), store=None)
    render.render_mcp(cfg, camp, fake_binding(tmp_path))
    servers = json.loads((camp / ".mcp.json").read_text())["mcpServers"]
    assert servers["mneme"]["command"].endswith("/bin/mneme")
    assert servers["mempalace"] == {"keep": 1}  # untouched without a store
    fresh = tmp_path / "d"
    fresh.mkdir()
    render.render_mcp(cfg, fresh, fake_binding(tmp_path))
    assert list(json.loads((fresh / ".mcp.json").read_text())["mcpServers"]) == ["mneme"]


def _unstored_cfg():
    from mneme.mempalace.models import CampaignMempalaceConfig

    return CampaignMempalaceConfig(campaign="c", recipe_version="4.0.0", wings=(), store=None)


def test_path_decoy_never_wins_in_rendered_entry(tmp_path, monkeypatch):
    root, camp, entity, runner = _managed(tmp_path, monkeypatch)
    _touch_exe(tmp_path / "decoy" / "mempalace-mcp")
    _touch_exe(tmp_path / "decoy" / "mneme")
    monkeypatch.setenv("PATH", f"{tmp_path / 'decoy'}:{os.environ['PATH']}")
    bringup.bringup(entity, "stormhaven", runner=runner, do_backup=False)
    servers = json.loads((camp / ".mcp.json").read_text())["mcpServers"]
    assert servers["mempalace"]["command"] == str(tmp_path / ".fake-venv/bin/mempalace-mcp")
    assert servers["mneme"]["command"] == str(tmp_path / ".fake-venv/bin/mneme")


def test_bringup_missing_program_writes_nothing(tmp_path, monkeypatch):
    root, camp, entity, runner = _managed(tmp_path, monkeypatch)
    cj = tmp_path / "home" / ".mempalace" / "config.json"
    (tmp_path / ".fake-venv/bin/mempalace-mcp").unlink()
    before = _snapshot(camp, cj) if cj.exists() else _snapshot(camp)
    report = bringup.bringup(entity, "stormhaven", runner=runner, do_backup=False)
    assert not report.ready
    notes = " ".join(s.note or "" for s in report.steps)
    assert "mempalace-mcp program missing" in notes and "nothing written" in notes
    after = _snapshot(camp, cj) if cj.exists() else _snapshot(camp)
    assert after == before
    assert not cj.exists()


def test_existing_faces_missing_program_writes_nothing(tmp_path, monkeypatch):
    root, camp, entity, runner = _managed(tmp_path, monkeypatch)
    cj = tmp_path / "home" / ".mempalace" / "config.json"
    assert bringup.bringup(entity, "stormhaven", runner=runner, do_backup=False).ready
    (tmp_path / ".fake-venv/bin/mempalace-mcp").unlink()
    before = _snapshot(camp, cj)
    assert {Path(k).name for k in before} >= {
        "mempalace.yaml", ".mempalaceignore", "config.yaml", "config.json", ".mcp.json"
    }
    with pytest.raises(McpBindingError, match="mempalace-mcp"):
        bringup.render_existing_faces(entity, "stormhaven")
    assert _snapshot(camp, cj) == before


def test_foreign_campaign_faces_write_no_mcp_json(tmp_path):
    root = tmp_path / "campaigns"
    foreign = make_simple_campaign(root, "obelisk")
    ownership.write_owner(foreign, ID_B)
    entity = entity_for_trees(root, identity=ID_A)
    before = _snapshot(foreign)
    with pytest.raises(discover.DiscoveryError, match="identity adopt"):
        bringup.render_existing_faces(entity, "obelisk")
    with pytest.raises(discover.DiscoveryError, match="identity adopt"):
        bringup.bringup(entity, "obelisk", do_backup=False)
    assert not (foreign / ".mcp.json").exists()
    assert _snapshot(foreign) == before


# ── file_reasons (008 US3) ────────────────────────────────────────────────────────


def _fr_setup(tmp_path, env=None):
    from mneme.mempalace.mcpface import file_reasons  # noqa: F401

    b = fake_binding(tmp_path, env)
    store = tmp_path / "store"
    f = tmp_path / "x.json"
    merge_write(f, {"mneme": mneme_entry(b), "mempalace": mempalace_entry(b, store)})
    return b, store, f


def test_file_reasons_coherent(tmp_path):
    from mneme.mempalace.mcpface import file_reasons

    b, store, f = _fr_setup(tmp_path)
    assert file_reasons(f, ".mcp.json", b, store) == []
    assert file_reasons(f, ".mcp.json", b, None) == []


def test_file_reasons_missing_and_unreadable(tmp_path):
    from mneme.mempalace.mcpface import file_reasons

    b = fake_binding(tmp_path)
    f = tmp_path / "nope.json"
    assert file_reasons(f, "root .mcp.json", b, None) == ["mcp: root .mcp.json missing"]
    for text in ("{bad", "[]", '{"mcpServers": []}'):
        f.write_text(text)
        assert file_reasons(f, ".mcp.json", b, None) == ["mcp: .mcp.json unreadable"]


def test_file_reasons_each_mismatch(tmp_path):
    from mneme.mempalace.mcpface import file_reasons

    b, store, f = _fr_setup(tmp_path)
    d = json.loads(f.read_text())
    s = d["mcpServers"]
    s["mneme"]["command"] = "mneme"
    s["mneme"]["args"] = ["mp", "mcp"]
    s["mempalace"]["command"] = "mempalace-mcp"
    s["mempalace"]["env"]["MEMPALACE_PALACE_PATH"] = "/other"
    f.write_text(json.dumps(d))
    r = file_reasons(f, ".mcp.json", b, store)
    assert r == [
        f"mcp: .mcp.json mneme command != {b.mneme_program}",
        f"mcp: .mcp.json mneme config != {b.config_path}",
        f"mcp: .mcp.json mempalace command != {b.mempalace_program}",
        "mcp: .mcp.json mempalace palace != store path",
    ]
    # store-less: mempalace entry is not examined
    assert len(file_reasons(f, ".mcp.json", b, None)) == 2


def test_file_reasons_missing_servers_and_env(tmp_path):
    from mneme.mempalace.mcpface import file_reasons

    b, store, f = _fr_setup(tmp_path)
    f.write_text('{"mcpServers": {}}')
    assert file_reasons(f, ".mcp.json", b, store) == [
        "mcp: .mcp.json has no mneme server",
        "mcp: .mcp.json has no mempalace server",
    ]
    declared = fake_binding(tmp_path, {"MEMPALACE_EMBEDDING_MODEL": "m"})
    merge_write(f, {"mneme": mneme_entry(b), "mempalace": mempalace_entry(b, store)})
    assert file_reasons(f, ".mcp.json", declared, store) == [
        "mcp: .mcp.json embedder/backend env out of date (MEMPALACE_EMBEDDING_MODEL)"
    ]


# ── clone-root rule (008 US4) ─────────────────────────────────────────────────────


def _clone_campaign(tmp_path, entity_id=ID_A, base=None, tree_name="clone", name="toee"):
    """A clone root with shared folders and one owned campaign (with a store alias)."""
    tree = tmp_path / tree_name
    for d in ("gm-assistant", "scripts", ".claude"):
        (tree / d).mkdir(parents=True, exist_ok=True)
    camp = make_simple_campaign(tree, name)
    ownership.write_owner(camp, entity_id)
    (camp / ".mneme").mkdir(exist_ok=True)
    (camp / ".mneme" / "mempalace.yaml").write_text(
        f"campaign: {name}\nrecipe_version: '2.0.0'\nstore:\n  alias: {name}\n"
        f"wings:\n  - name: {name}\n    source: .\n    trust: reference\n    rooms: []\n"
    )
    return tree, camp


def _clone_entity(tree, identity=ID_A, shared=("gm-assistant", "scripts"), mempalace=None):
    return replace(
        entity_for_trees(tree, identity=identity, mempalace=mempalace or tree.parent / "mp"),
        campaign_shared_dirs=shared,
    )


def _layout(entity, name="toee"):
    return bringup.faces_layout(entity, name)


def test_layout_single(tmp_path):
    tree, camp = _clone_campaign(tmp_path)
    lay = _layout(_clone_entity(tree))
    assert lay.verdict == "SINGLE" and lay.root == tree and lay.campaigns == ("toee",)
    assert lay.reason == f"single-campaign clone {tree}"


def test_single_renders_both_entries_at_root_and_preserves_others(tmp_path):
    tree, camp = _clone_campaign(tmp_path)
    (tree / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"campaign": {"type": "stdio", "command": "x"}}})
    )
    entity = _clone_entity(tree)
    written = bringup.render_existing_faces(entity, "toee")
    assert tree / ".mcp.json" in written
    servers = json.loads((tree / ".mcp.json").read_text())["mcpServers"]
    assert set(servers) == {"campaign", "mneme", "mempalace"}
    assert servers == json.loads((camp / ".mcp.json").read_text())["mcpServers"] | {
        "campaign": {"type": "stdio", "command": "x"}
    }


def test_dot_dirs_and_symlinks_not_counted(tmp_path):
    tree, camp = _clone_campaign(tmp_path)
    (tree / ".hidden").mkdir()
    (tree / "link").symlink_to(tmp_path)
    lay = _layout(_clone_entity(tree))
    assert lay.campaigns == ("toee",) and lay.verdict == "SINGLE"


def _second_campaign(tree):
    make_simple_campaign(tree, "other")


def test_multi_never_touches_root(tmp_path):
    tree, camp = _clone_campaign(tmp_path)
    _second_campaign(tree)
    entity = _clone_entity(tree)
    lay = _layout(entity)
    assert lay.verdict == "MULTI" and lay.campaigns == ("other", "toee")
    assert "holds 2 campaigns (other, toee)" in lay.reason
    written = bringup.render_existing_faces(entity, "toee")
    assert tree / ".mcp.json" not in written and not (tree / ".mcp.json").exists()


def test_conflict_leaves_root_byte_identical(tmp_path):
    import hashlib

    tree, camp = _clone_campaign(tmp_path)
    _second_campaign(tree)
    (tree / ".mcp.json").write_text(json.dumps({"mcpServers": {"mneme": {"command": "old"}}}))
    before = hashlib.sha256((tree / ".mcp.json").read_bytes()).hexdigest()
    entity = _clone_entity(tree)
    lay = _layout(entity)
    assert lay.verdict == "CONFLICT" and lay.root_has_mneme_entries
    assert "kostadis/campaigns#672" in lay.reason and "(mneme)" in lay.reason
    bringup.render_existing_faces(entity, "toee")
    assert hashlib.sha256((tree / ".mcp.json").read_bytes()).hexdigest() == before


def test_undeclared_shared_set_owes_and_lists_children(tmp_path):
    tree, camp = _clone_campaign(tmp_path)
    entity = _clone_entity(tree, shared=None)
    lay = _layout(entity)
    assert lay.verdict == "UNDECLARED" and not lay.shared_declared
    assert lay.reason.endswith("holds: gm-assistant, scripts, toee")
    # undeclared + root entries is still UNDECLARED (cannot claim a conflict it cannot see)
    (tree / ".mcp.json").write_text(json.dumps({"mcpServers": {"mneme": {}}}))
    assert _layout(entity).verdict == "UNDECLARED"
    bringup.render_existing_faces(entity, "toee")
    assert json.loads((tree / ".mcp.json").read_text()) == {"mcpServers": {"mneme": {}}}


def test_campaign_named_in_shared_set_is_undeclared_style(tmp_path):
    tree, camp = _clone_campaign(tmp_path)
    lay = _layout(_clone_entity(tree, shared=("gm-assistant", "scripts", "toee")))
    assert lay.verdict == "UNDECLARED" and "toee" in lay.reason and "collide" in lay.reason


def test_dir_outside_declared_tree_is_no_clone(tmp_path):
    tree, camp = _clone_campaign(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    other = make_simple_campaign(elsewhere, "solo")
    ownership.write_owner(other, ID_A)
    entity = _clone_entity(tree)
    ref = discover.ref_for_dir(entity, other)
    from mneme.mempalace.mcpface import clone_layout

    assert clone_layout(ref, entity).verdict == "NO_CLONE"
    assert clone_layout(SimpleNamespace(path=other, tree=None), entity).verdict == "NO_CLONE"
    assert not (elsewhere / ".mcp.json").exists()


def test_two_mnemes_never_cross_write(tmp_path):
    a_base, b_base = tmp_path / "a", tmp_path / "b"
    a_tree, a_camp = _clone_campaign(a_base, ID_A, tree_name="clone", name="toee")
    b_tree, b_camp = _clone_campaign(b_base, ID_B, tree_name="clone", name="obelisk")
    ent_a = _clone_entity(a_tree, ID_A, mempalace=a_base / "mp")
    ent_b = _clone_entity(b_tree, ID_B, mempalace=b_base / "mp")
    # entity_for_trees put each fake owner beside its own tree's parent, so the two differ
    assert ent_a.venv != ent_b.venv and ent_a.source_path != ent_b.source_path
    bringup.render_existing_faces(ent_a, "toee")
    bringup.render_existing_faces(ent_b, "obelisk")
    for tree, camp, ent, other in ((a_tree, a_camp, ent_a, ent_b), (b_tree, b_camp, ent_b, ent_a)):
        for f in (camp / ".mcp.json", tree / ".mcp.json"):
            text = f.read_text()
            assert str(ent.venv) in text and str(ent.source_path) in text
            assert str(other.venv) not in text and str(other.source_path) not in text
    # A cannot render B's campaign, and nothing appears in B's clone from that attempt
    (b_tree / ".mcp.json").unlink()
    before = _snapshot(b_tree)
    with pytest.raises(discover.DiscoveryError):
        bringup.render_existing_faces(ent_a, "obelisk", campaign_dir=str(b_camp))
    assert _snapshot(b_tree) == before and not (b_tree / ".mcp.json").exists()
