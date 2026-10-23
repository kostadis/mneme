"""`mp prune` for corpus campaigns and the former-canon guard (feature 007, T031, FR-018a)."""

from __future__ import annotations

import json

import pytest

from mneme.mempalace import authority, former_wings, prune, refresh, render
from mneme.mempalace import recipe as recipe_mod
from mneme.mempalace.prune import PruneAbort
from tests.fixtures import add_store_pointer, make_campaigns
from tests.fixtures.corpus_campaign import DECLARED, corpus_world

DECOY = "docs/campaign_state_draft.md"


@pytest.fixture
def w(tmp_path, monkeypatch):
    world = corpus_world(tmp_path, monkeypatch)
    cfg = authority.load(world.camp, mempalace_root=world.store.parent.parent)
    render.write_all(cfg, recipe_mod.current(), world.camp)
    (res,) = refresh.refresh(world.entity, campaign="corp", runner=world.runner)
    assert not res.failed, res.error
    return world


def decoy(w, wing="root"):
    w.runner.mine_files(w.camp, [DECOY], wing=wing, palace=w.store)


def run(w, **kw):
    out: list[str] = []
    ok = prune.prune(w.entity, "corp", runner=w.runner, emit=out.append, **kw)
    return ok, out


def test_refused_without_the_flag_when_the_wing_was_authoritative(w):
    former_wings.write(w.store, "corp", {"root": "authoritative", "reference": "reference"})
    decoy(w)
    with pytest.raises(PruneAbort, match="root"):
        run(w, confirm=True, expect=1)
    assert DECOY in w.source_rels()  # nothing was deleted
    assert not any(ln.startswith("forget") and "--apply" in ln for ln in w.log_lines())


def test_preview_names_the_former_canon_wing_with_counts(w):
    former_wings.write(w.store, "corp", {"root": "authoritative"})
    decoy(w)
    ok, out = run(w)
    assert ok
    assert any("former-canon wing 'root': 1 file(s), 1 drawers" in ln for ln in out)
    assert any("--include-former-canon root" in ln for ln in out)


def test_proceeds_when_every_former_canon_wing_is_named(w):
    former_wings.write(w.store, "corp", {"root": "authoritative"})
    decoy(w)
    ok, out = run(w, confirm=True, expect=1, include_former_canon=("root",))
    assert ok, out
    assert w.source_rels() == set(DECLARED)


def test_a_non_authoritative_former_wing_needs_no_flag(w):
    former_wings.write(w.store, "corp", {"root": "reference"})
    decoy(w)
    ok, out = run(w, confirm=True, expect=1)
    assert ok, out
    assert w.source_rels() == set(DECLARED)


def test_absent_record_treats_every_wing_holding_undeclared_drawers_as_former_canon(w):
    assert former_wings.read(w.store) is None
    decoy(w, wing="summaries")  # a wing named like a kind is still caught: keyed on sources
    with pytest.raises(PruneAbort, match="summaries"):
        run(w, confirm=True, expect=1)
    ok, out = run(w, confirm=True, expect=1, include_former_canon=("summaries",))
    assert ok, out


def test_unreadable_record_fails_closed(w):
    former_wings.record_path(w.store).write_text("{not json")
    decoy(w)
    with pytest.raises(PruneAbort):
        run(w, confirm=True, expect=1)


def test_naming_an_unrelated_wing_does_not_unlock_another(w):
    former_wings.write(w.store, "corp", {"root": "authoritative"})
    decoy(w)
    with pytest.raises(PruneAbort):
        run(w, confirm=True, expect=1, include_former_canon=("npcs",))


def test_nothing_to_prune_on_an_exact_palace(w):
    ok, out = run(w)
    assert ok and any("nothing to prune" in ln for ln in out)


def test_invalid_declaration_stops_the_prune(w):
    from mneme.mempalace.runner import MempalaceError

    decoy(w)
    p = w.camp / ".mneme" / "corpus.yaml"
    p.write_text(p.read_text().replace("npcs:", "npcz:"))
    with pytest.raises(MempalaceError, match="cannot prune"):
        run(w, confirm=True, expect=1, include_former_canon=("root",))
    assert DECOY in w.source_rels()


def test_unreadable_palace_stops_the_prune(w, monkeypatch):
    from mneme.mempalace.runner import MempalaceError

    monkeypatch.setenv("MNEME_STUB_SOURCES", "rc1")
    with pytest.raises(MempalaceError, match="cannot read"):
        run(w)


def test_a_forget_that_did_not_take_fails_the_reverify(w, monkeypatch):
    decoy(w)
    former_wings.write(w.store, "corp", {})
    real = w.runner.forget
    monkeypatch.setattr(w.runner, "forget", lambda *a, **k: real(*a, **{**k, "apply": False}))
    ok, out = run(w, confirm=True, expect=1)
    assert not ok and any(ln.startswith("FAIL prune") and "remain" in ln for ln in out)


# ── the former-wings record ──────────────────────────────────────────────────


def test_record_roundtrip_and_shape(tmp_path):
    former_wings.write(tmp_path, "c", {"a": "authoritative", "b": "reference"})
    doc = json.loads(former_wings.record_path(tmp_path).read_text())
    assert doc["schema"] == 1 and doc["campaign"] == "c" and "recorded_at" in doc
    assert doc["wings"] == {"a": "authoritative", "b": "reference"}
    assert former_wings.read(tmp_path).authoritative() == {"a"}


def test_try_record_is_best_effort(tmp_path, monkeypatch):
    class W:
        name, trust = "root", "authoritative"

    class S:
        path = tmp_path

    class Cfg:
        campaign, wings, store = "c", (W(),), S()

    def boom(*a, **k):
        raise OSError("read-only")

    monkeypatch.setattr(former_wings, "write", boom)
    assert "WARN" in former_wings.try_record(Cfg())  # a warning, never an exception


def test_try_record_never_creates_a_missing_store(tmp_path):
    class S:
        path = tmp_path / "nope"

    class W:
        name, trust = "root", "authoritative"

    class Cfg:
        campaign, wings, store = "c", (W(),), S()

    assert former_wings.try_record(Cfg()) is None and not (tmp_path / "nope").exists()


def test_wing_model_status_and_refresh_record_the_wings(tmp_path, monkeypatch):
    import subprocess
    import sys

    from mneme.mempalace import conform
    from mneme.mempalace.runner import MempalaceRunner
    from tests.fixtures import STUB

    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    def stub(cmd):
        return subprocess.run([sys.executable, str(STUB), *cmd[1:]], capture_output=True, text=True)

    from tests.fixtures import entity_for

    root = make_campaigns(tmp_path / "campaigns")
    add_store_pointer(root, "full")
    mp = tmp_path / "mp"
    entity = entity_for(root, mempalace=mp)
    cfg = authority.load(root / "full", mempalace_root=mp)
    cfg.store.path.mkdir(parents=True)
    runner = MempalaceRunner("mempalace", stub)
    conform.report(entity, "full", runner=runner)
    rec = former_wings.read(cfg.store.path)
    assert rec is not None and set(rec.wings) == {w.name for w in cfg.wings}
    former_wings.record_path(cfg.store.path).unlink()
    refresh.refresh(entity, campaign="full", runner=runner)
    assert former_wings.read(cfg.store.path) is not None
