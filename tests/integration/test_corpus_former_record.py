"""A store built from the corpus records NO former wings (GM 2026-10-24, FR-018a).

`mp regenerate --confirm` and a bring-up into a store that did not exist write an empty
former-wings record, so `mp prune` needs no `--include-former-canon` there. A refresh or
bring-up into an EXISTING store without a record writes nothing and stays fail-closed; a
wing-model refresh still records its wings.
"""

from __future__ import annotations

import pytest

from mneme.mempalace import authority, backup, bringup, former_wings, prune, refresh, render
from mneme.mempalace import recipe as recipe_mod
from mneme.mempalace.prune import PruneAbort
from tests.fixtures.corpus_campaign import corpus_world

DECOY = "docs/campaign_state_draft.md"


def _prune(w, **kw):
    out: list[str] = []
    ok = prune.prune(w.entity, "corp", runner=w.runner, emit=out.append, **kw)
    return ok, out


def _decoy(w, wing="root"):
    w.runner.mine_files(w.camp, [DECOY], wing=wing, palace=w.store)


def _assert_empty_record(store):
    rec = former_wings.read(store)
    assert rec is not None and rec.wings == {} and rec.authoritative() == frozenset()


def _prunes_without_the_flag(w):
    _decoy(w)  # an undeclared file in the root wing
    ok, out = _prune(w)  # preview
    assert ok and not any("NEEDS --include-former-canon" in ln for ln in out), out
    ok, out = _prune(w, confirm=True, expect=1)
    assert ok, out
    assert DECOY not in w.source_rels()


def test_empty_record_round_trips_distinct_from_absent(tmp_path):
    assert former_wings.read(tmp_path) is None
    assert former_wings.try_record_empty(tmp_path, "c") is None
    _assert_empty_record(tmp_path)


def test_try_record_empty_failure_is_a_warning(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(former_wings, "write", boom)
    assert "WARN" in former_wings.try_record_empty(tmp_path, "c")


def test_regenerate_writes_an_empty_record_and_prune_needs_no_flag(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    cfg = authority.load(w.camp, mempalace_root=w.store.parent.parent)
    render.write_all(cfg, recipe_mod.current(), w.camp)
    (res,) = refresh.refresh(w.entity, campaign="corp", runner=w.runner)
    assert not res.failed, res.error
    assert former_wings.read(w.store) is None  # a corpus refresh records nothing
    real_rmtree = backup.shutil.rmtree

    def clear(path, *a, **k):  # the stub keeps its drawers outside the store dir
        real_rmtree(path, *a, **k)
        w.state.unlink(missing_ok=True)

    monkeypatch.setattr(backup.shutil, "rmtree", clear)
    fm = backup.regenerate(w.entity, "corp", runner=w.runner)
    assert fm.record_warning is None
    _assert_empty_record(w.store)
    _prunes_without_the_flag(w)


def test_bringup_into_a_fresh_store_writes_an_empty_record(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch, authority=False)
    assert not w.store.exists()
    report = bringup.bringup(
        w.entity, "corp", runner=w.runner, config_json=tmp_path / "config.json", do_backup=False
    )
    assert report.ready, [(s.name, s.state, s.note) for s in report.steps]
    _assert_empty_record(w.store)
    _prunes_without_the_flag(w)


def test_bringup_into_an_existing_store_writes_nothing_and_prune_fails_closed(
    tmp_path, monkeypatch
):
    w = corpus_world(tmp_path, monkeypatch, authority=False)
    w.store.mkdir(parents=True)  # the store pre-exists (it may hold old wings)
    report = bringup.bringup(
        w.entity, "corp", runner=w.runner, config_json=tmp_path / "config.json", do_backup=False
    )
    assert report.ready, [(s.name, s.state, s.note) for s in report.steps]
    assert former_wings.read(w.store) is None
    _decoy(w)
    with pytest.raises(PruneAbort, match="root"):
        _prune(w, confirm=True, expect=1)
    assert DECOY in w.source_rels()


def test_corpus_refresh_into_an_existing_store_writes_nothing(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    cfg = authority.load(w.camp, mempalace_root=w.store.parent.parent)
    render.write_all(cfg, recipe_mod.current(), w.camp)
    (res,) = refresh.refresh(w.entity, campaign="corp", runner=w.runner)
    assert not res.failed, res.error
    (res,) = refresh.refresh(w.entity, campaign="corp", runner=w.runner)
    assert former_wings.read(w.store) is None
    _decoy(w)
    with pytest.raises(PruneAbort, match="root"):
        _prune(w, confirm=True, expect=1)
