"""GH #26b — embedding-dimension guard: built-dim read, mempalace-reported dim, fail-closed."""

from __future__ import annotations

import dataclasses
import sqlite3
import subprocess
import sys

import pytest

from mneme.mempalace import authority, backup, bringup, conform, provision, refresh
from mneme.mempalace import embedder_guard as g
from mneme.mempalace.models import CampaignMempalaceConfig, State, StorePointer, Wing
from mneme.mempalace.runner import MempalaceError, MempalaceRunner
from tests.fixtures import entity_for, make_greenfield_campaign

OLLAMA = {
    "MEMPALACE_EMBEDDING_PROVIDER": "ollama",
    "MEMPALACE_EMBEDDING_MODEL": "qwen3-embedding:0.6b",
    "MEMPALACE_EMBEDDING_ENDPOINT": "http://spark:11434",
}


def make_store(store, dims: dict[str, int | None], next_uid: dict[str, int] | None = None) -> None:
    """dims value None = meta table with NO dim row (a created-but-empty collection unless
    ``next_uid[coll] > 0``)."""
    for coll, dim in dims.items():
        d = store / "turbovec" / coll
        d.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(d / "store.sqlite3")
        con.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)")
        con.execute("INSERT INTO meta VALUES('embedder_identity','embed')")
        if dim is not None:
            con.execute("INSERT INTO meta VALUES('dim', ?)", (str(dim),))
        if next_uid and coll in next_uid:
            con.execute("INSERT INTO meta VALUES('next_uid', ?)", (str(next_uid[coll]),))
        con.commit()
        con.close()


def with_env(entity, env):
    return dataclasses.replace(entity, env=env)


def prober_for(dim):
    calls = []

    def p(entity):
        calls.append(entity)
        return dim

    p.calls = calls
    return p


# ---- built_dimension -------------------------------------------------------------------
def test_built_dimension_reads_dim(tmp_path):
    make_store(tmp_path, {"a": 1024})
    assert g.built_dimension(tmp_path) == 1024


def test_built_dimension_missing_and_garbage(tmp_path):
    assert g.built_dimension(tmp_path / "nope") is None
    d = tmp_path / "turbovec" / "a"
    d.mkdir(parents=True)
    (d / "store.sqlite3").write_bytes(b"not a database at all" * 50)
    assert g.built_dimension(tmp_path) is None
    assert g.built_dimensions(tmp_path) == {"a": None}


def test_built_dimension_unparseable_value(tmp_path):
    make_store(tmp_path, {"a": None}, next_uid={"a": 5})
    con = sqlite3.connect(tmp_path / "turbovec" / "a" / "store.sqlite3")
    con.execute("INSERT INTO meta VALUES('dim','abc')")
    con.commit()
    con.close()
    assert g.built_dimension(tmp_path) is None
    assert g.built_dimensions(tmp_path) == {"a": None}


def test_built_dimension_disagreeing_collections(tmp_path):
    make_store(tmp_path, {"a": 384, "b": 1024})
    assert g.built_dimensions(tmp_path) == {"a": 384, "b": 1024}
    assert g.built_dimension(tmp_path) is None
    r = g.check(entity_for(tmp_path), tmp_path, prober_for(384))
    assert r.state is g.GuardState.MISMATCH and "disagree" in r.message


def test_created_but_empty_collection_is_not_unknown(tmp_path):
    e = with_env(entity_for(tmp_path), OLLAMA)
    make_store(tmp_path / "s", {"drawers": 1024, "closets": None})
    assert g.built_dimensions(tmp_path / "s") == {"drawers": 1024}
    assert g.check(e, tmp_path / "s", prober_for(1024)).state is g.GuardState.OK
    make_store(tmp_path / "t", {"drawers": None, "closets": None}, next_uid={"closets": 0})
    assert g.check(e, tmp_path / "t", prober_for(1024)).state is g.GuardState.EMPTY
    # has rows but no dim row => corrupt => unknown
    make_store(tmp_path / "u", {"drawers": None}, next_uid={"drawers": 3})
    assert g.check(e, tmp_path / "u", prober_for(1024)).state is g.GuardState.UNKNOWN


# ---- expected dimension / check ----------------------------------------------------------
def test_expected_dimension_delegates_to_prober(tmp_path):
    e = with_env(entity_for(tmp_path), OLLAMA)
    p = prober_for(1024)
    assert g.expected_dimension(e, p) == 1024 and p.calls == [e]
    assert g.expected_dimension(e, prober_for(None)) is None


def test_check_states(tmp_path):
    e = with_env(entity_for(tmp_path), OLLAMA)
    assert g.check(e, tmp_path / "none", prober_for(1)).state is g.GuardState.EMPTY
    make_store(tmp_path / "s1", {"c": 1024})
    ok = g.check(e, tmp_path / "s1", prober_for(1024))
    assert ok.state is g.GuardState.OK and "1024" in ok.message
    assert "ollama:qwen3-embedding:0.6b" in ok.message
    bad = g.check(e, tmp_path / "s1", prober_for(768))
    assert bad.state is g.GuardState.MISMATCH
    assert "1024" in bad.message and "768" in bad.message and "regenerate" in bad.message
    unk = g.check(e, tmp_path / "s1", prober_for(None))
    assert unk.state is g.GuardState.UNKNOWN and "regenerate <campaign>" not in unk.message
    undecl = g.check(entity_for(tmp_path), tmp_path / "s1", prober_for(1024))
    assert undecl.state is g.GuardState.OK and "not declared in hypostasis.yaml" in undecl.message


def test_unreadable_plus_readable_collection_is_unknown(tmp_path):
    make_store(tmp_path, {"a": 384})
    d = tmp_path / "turbovec" / "b"
    d.mkdir(parents=True)
    (d / "store.sqlite3").write_bytes(b"garbage" * 100)
    r = g.check(entity_for(tmp_path), tmp_path, prober_for(384))
    assert r.state is g.GuardState.UNKNOWN and "b" in r.message


def test_non_turbovec_backend_with_files_is_unknown(tmp_path):
    e = with_env(entity_for(tmp_path), {"MEMPALACE_BACKEND": "chroma"})
    store = tmp_path / "s"
    store.mkdir()
    assert g.check(e, store, prober_for(1)).state is g.GuardState.EMPTY
    (store / "chroma.sqlite3").write_text("x")
    assert g.check(e, store, prober_for(1)).state is g.GuardState.UNKNOWN


def test_collection_without_readable_store_is_unknown_not_empty(tmp_path):
    d = tmp_path / "s" / "turbovec" / "c"
    d.mkdir(parents=True)
    (d / "index.tvim").write_text("idx")
    r = g.check(entity_for(tmp_path), tmp_path / "s", prober_for(1024))
    assert r.state is g.GuardState.UNKNOWN and r.blocks_write


def test_foreign_vector_artifacts_are_unknown_not_empty(tmp_path):
    e = entity_for(tmp_path)  # backend unset
    s = tmp_path / "s"
    s.mkdir()
    (s / "chroma.sqlite3").write_text("x")
    r = g.check(e, s, prober_for(384))
    assert r.state is g.GuardState.UNKNOWN and "chroma.sqlite3" in r.message
    (s / "chroma.sqlite3").unlink()
    (s / "abcd-uuid-segment").mkdir()  # chroma/other-backend dir
    assert g.check(e, s, prober_for(384)).state is g.GuardState.UNKNOWN
    # dead legacy chroma ALONGSIDE readable turbovec content: turbovec decides
    t = tmp_path / "t"
    make_store(t, {"c": 384})
    (t / "chroma.sqlite3").write_text("x")
    assert g.check(e, t, prober_for(384)).state is g.GuardState.OK


def test_non_vector_files_do_not_count_as_vectors(tmp_path):
    s = tmp_path / "s"
    (s / "turbovec").mkdir(parents=True)
    (s / "knowledge_graph.sqlite3").write_text("kg")
    assert g.check(entity_for(tmp_path), s, prober_for(1024)).state is g.GuardState.EMPTY


# ---- the real subprocess prober (offline: a fake `mempalace` package on PYTHONPATH) -----------
def _fake_mempalace(tmp_path, body):
    pkg = tmp_path / "fakepkg" / "mempalace"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "embedding.py").write_text(body)
    return {"PYTHONPATH": str(tmp_path / "fakepkg")}


@pytest.fixture
def _use_sys_python(monkeypatch):
    monkeypatch.setattr(g, "_mempalace_python", lambda entity: sys.executable)


def test_real_prober_reads_dim_from_mempalace(tmp_path, _use_sys_python):
    env = _fake_mempalace(tmp_path, "def probe_dimension():\n    print('noise')\n    return 1024\n")
    e = with_env(entity_for(tmp_path), env)
    assert g.probe_dimension(e) == 1024


def _spawn_counter(monkeypatch):
    calls = []
    real_run = subprocess.run
    monkeypatch.setattr(
        g.subprocess, "run", lambda *a, **kw: calls.append(kw) or real_run(*a, **kw)
    )
    return calls


def test_real_prober_zero_or_crash_is_unknown(tmp_path, monkeypatch, _use_sys_python):
    calls = _spawn_counter(monkeypatch)
    cases = {
        "z": "def probe_dimension():\n    return 0\n",
        "b": "def probe_dimension():\n    raise SystemExit(3)\n",
        "j": "def probe_dimension():\n    return 'x'\n",
    }
    for i, (name, body) in enumerate(cases.items(), 1):
        g._probe_cache.clear()
        env = _fake_mempalace(tmp_path / name, body)
        assert g.probe_dimension(with_env(entity_for(tmp_path), env)) is None
        assert len(calls) == i  # each case really spawned a probe


def test_real_prober_caches_failures_and_uses_merged_env(tmp_path, monkeypatch, _use_sys_python):
    env = _fake_mempalace(tmp_path, "def probe_dimension():\n    return 0\n")
    e = with_env(entity_for(tmp_path), env)
    calls = []
    real_run = subprocess.run
    monkeypatch.setattr(
        g.subprocess, "run", lambda *a, **kw: calls.append(kw["env"]) or real_run(*a, **kw)
    )
    assert g.probe_dimension(e) is None and g.probe_dimension(e) is None
    assert len(calls) == 1 and calls[0]["PYTHONPATH"] == env["PYTHONPATH"]


def test_cached_failure_keeps_reason_and_expires_after_ttl(
    tmp_path, monkeypatch, _use_sys_python
):
    env = _fake_mempalace(tmp_path, "def probe_dimension():\n    raise SystemExit(3)\n")
    e = with_env(entity_for(tmp_path), env)
    calls = _spawn_counter(monkeypatch)
    now = [1000.0]
    monkeypatch.setattr(g.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(g, "default_prober", g.probe_dimension)
    make_store(tmp_path / "s", {"c": 1024})
    first = g.check(e, tmp_path / "s")
    assert "rc 3" in first.message and "embedder down?" not in first.message
    now[0] += g.PROBE_FAILURE_TTL - 1
    second = g.check(e, tmp_path / "s")  # cached: no new spawn, SAME specific reason
    assert len(calls) == 1 and "rc 3" in second.message
    now[0] += 2  # past the TTL
    g.check(e, tmp_path / "s")
    assert len(calls) == 2


def test_successful_probe_stays_cached_past_ttl(tmp_path, monkeypatch, _use_sys_python):
    env = _fake_mempalace(tmp_path, "def probe_dimension():\n    return 8\n")
    e = with_env(entity_for(tmp_path), env)
    calls = _spawn_counter(monkeypatch)
    now = [1000.0]
    monkeypatch.setattr(g.time, "monotonic", lambda: now[0])
    assert g.probe_dimension(e) == 8
    now[0] += g.PROBE_FAILURE_TTL * 100
    assert g.probe_dimension(e) == 8
    assert len(calls) == 1


def test_no_interpreter_is_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr(g, "_mempalace_python", lambda entity: None)
    assert g.probe_dimension(entity_for(tmp_path)) is None


def _path_mempalace(tmp_path, text, name="pathbin"):
    d = tmp_path / name
    d.mkdir()
    (d / "mempalace").write_text(text)
    (d / "mempalace").chmod(0o755)
    return d


def test_interpreter_venv_sibling_python(tmp_path):
    b = tmp_path / "bin"
    b.mkdir()
    (b / "mempalace").write_text("#!/nope\n")
    (b / "python").write_text("")
    e = dataclasses.replace(entity_for(tmp_path), venv=tmp_path)
    assert g._mempalace_python(e) == str(b / "python")


def test_interpreter_path_binary_shebang_uses_merged_path(tmp_path):
    d = _path_mempalace(tmp_path, "#!/opt/py/bin/python3\nprint()\n")
    e = with_env(entity_for(tmp_path), {"PATH": str(d)})  # entity.env PATH wins (merged)
    assert g._mempalace_python(e) == "/opt/py/bin/python3"


def test_interpreter_env_shebang_and_sh_trampoline(tmp_path):
    d = _path_mempalace(tmp_path, "#!/usr/bin/env python3\n")
    (d / "python3").write_text("")
    (d / "python3").chmod(0o755)
    e = with_env(entity_for(tmp_path), {"PATH": str(d)})
    assert g._mempalace_python(e) == str(d / "python3")
    tramp = "#!/bin/sh\n'''exec' \"/opt/venv/bin/python\" \"$0\" \"$@\"\n' '''\n"
    d2 = _path_mempalace(tmp_path, tramp, "t")
    e2 = with_env(entity_for(tmp_path), {"PATH": str(d2)})
    assert g._mempalace_python(e2) == "/opt/venv/bin/python"
    (d2 / "mempalace").write_text("#!/bin/sh\necho hi\n")
    (d2 / "mempalace").chmod(0o755)
    assert g._mempalace_python(e2) is None


def test_no_interpreter_message(tmp_path, monkeypatch):
    monkeypatch.setattr(g, "default_prober", g.probe_dimension)
    e = with_env(entity_for(tmp_path), {"PATH": str(tmp_path / "empty")})
    make_store(tmp_path / "s", {"c": 1024})
    r = g.check(e, tmp_path / "s")
    assert r.state is g.GuardState.UNKNOWN and "cannot locate mempalace's interpreter" in r.message


def test_cache_key_includes_pythonpath_and_home(tmp_path, monkeypatch, _use_sys_python):
    calls = _spawn_counter(monkeypatch)
    base = _fake_mempalace(tmp_path / "a", "def probe_dimension():\n    return 8\n")
    g.probe_dimension(with_env(entity_for(tmp_path), {**base, "HOME": "/h1"}))
    g.probe_dimension(with_env(entity_for(tmp_path), {**base, "HOME": "/h2"}))
    other = _fake_mempalace(tmp_path / "b", "def probe_dimension():\n    return 9\n")
    assert g.probe_dimension(with_env(entity_for(tmp_path), {**other, "HOME": "/h2"})) == 9
    assert len(calls) == 3


def test_timeout_not_cached_and_has_own_message(tmp_path, monkeypatch, _use_sys_python):
    n = []

    def boom(*a, **kw):
        n.append(1)
        raise subprocess.TimeoutExpired("x", 1)

    monkeypatch.setattr(g.subprocess, "run", boom)
    monkeypatch.setattr(g, "default_prober", g.probe_dimension)
    e = entity_for(tmp_path)
    make_store(tmp_path / "s", {"c": 1024})
    r = g.check(e, tmp_path / "s")
    assert r.state is g.GuardState.UNKNOWN and "timed out" in r.message and "retry" in r.message
    g.check(e, tmp_path / "s")
    assert len(n) == 2  # not cached
    assert g.PROBE_TIMEOUT == 120.0


def test_probe_runs_from_neutral_cwd(tmp_path, monkeypatch, _use_sys_python):
    decoy = tmp_path / "decoy"
    (decoy / "mempalace").mkdir(parents=True)
    (decoy / "mempalace" / "__init__.py").write_text("")
    (decoy / "mempalace" / "embedding.py").write_text("def probe_dimension():\n    return 999\n")
    env = _fake_mempalace(tmp_path, "def probe_dimension():\n    return 1024\n")
    monkeypatch.chdir(decoy)
    calls = _spawn_counter(monkeypatch)
    assert g.probe_dimension(with_env(entity_for(tmp_path), env)) == 1024
    assert calls[0]["cwd"] != str(decoy)


# ---- guarded call sites ----------------------------------------------------------------
def _setup(tmp_path, monkeypatch, dims, env=OLLAMA, campaign="saga"):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    root = tmp_path / "campaigns"
    camp = root / campaign
    camp.mkdir(parents=True)
    store = tmp_path / "home" / ".mempalace" / "palaces" / campaign
    cfg = CampaignMempalaceConfig(
        campaign=campaign, recipe_version="1.0.0",
        wings=(Wing(campaign, ".", "reference", ()),),
        store=StorePointer(campaign, store),
    )
    authority.write(cfg, camp)
    (camp / "mempalace.yaml").write_text("wing: saga\nrooms: []\n")  # an existing wing
    store = authority.load(camp).store.path
    if dims is not None:
        make_store(store, dims)
    return with_env(entity_for(root), env), store, camp


def _runner():
    calls: list[list[str]] = []

    def run(cmd):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    return MempalaceRunner(binary="mempalace", runner=run), calls


def _mines(calls):
    return [c for c in calls if "mine" in c]


def test_first_mine_refuses_on_mismatch(tmp_path, monkeypatch):
    entity, store, camp = _setup(tmp_path, monkeypatch, {"c": 384})
    runner, calls = _runner()
    with pytest.raises(MempalaceError, match="mismatch"):
        provision.first_mine(
            authority.load(camp), camp, runner, entity=entity, prober=prober_for(1024)
        )
    assert _mines(calls) == []


def test_first_mine_unknown_empty_and_match(tmp_path, monkeypatch):
    entity, store, camp = _setup(tmp_path, monkeypatch, {"c": 1024})
    cfg = authority.load(camp)
    runner, calls = _runner()
    with pytest.raises(MempalaceError, match="cannot verify"):
        provision.first_mine(cfg, camp, runner, entity=entity, prober=prober_for(None))
    assert _mines(calls) == []
    provision.first_mine(cfg, camp, runner, entity=entity, prober=prober_for(1024))
    assert len(_mines(calls)) == 1


def test_first_mine_allows_empty_store(tmp_path, monkeypatch):
    entity, store, camp = _setup(tmp_path, monkeypatch, None)
    runner, calls = _runner()
    provision.first_mine(authority.load(camp), camp, runner, entity=entity, prober=prober_for(None))
    assert len(_mines(calls)) == 1


def test_refresh_refuses_on_mismatch_and_allows_match(tmp_path, monkeypatch):
    entity, store, camp = _setup(tmp_path, monkeypatch, {"c": 384})
    runner, calls = _runner()
    res = refresh.refresh(entity, campaign="saga", runner=runner, prober=prober_for(1024))
    assert res[0].failed and "mismatch" in res[0].error and _mines(calls) == []
    res = refresh.refresh(entity, campaign="saga", runner=runner, prober=prober_for(384))
    assert not res[0].failed and len(_mines(calls)) == 1
    cmd = _mines(calls)[0]
    assert cmd[cmd.index("--palace") + 1] == str(store)  # mines the palace it checked


def test_refresh_refuses_unknown(tmp_path, monkeypatch):
    entity, store, camp = _setup(tmp_path, monkeypatch, {"c": 384})
    runner, calls = _runner()
    res = refresh.refresh(entity, campaign="saga", runner=runner, prober=prober_for(None))
    assert res[0].failed and _mines(calls) == []


def test_refresh_fails_closed_on_bad_authority_skips_without_one(tmp_path, monkeypatch):
    entity, store, camp = _setup(tmp_path, monkeypatch, {"c": 384})
    runner, calls = _runner()
    auth = camp / ".mneme" / "mempalace.yaml"
    auth.write_text("campaign: [unterminated\n")
    res = refresh.refresh(entity, campaign="saga", runner=runner, prober=prober_for(384))
    assert res[0].failed and _mines(calls) == []
    auth.unlink()
    res = refresh.refresh(entity, campaign="saga", runner=runner, prober=prober_for(384))
    assert res[0].skipped and not res[0].failed and "bootstrap" in res[0].line()
    assert _mines(calls) == []


def test_refresh_no_store_pointer_message(tmp_path, monkeypatch):
    entity, store, camp = _setup(tmp_path, monkeypatch, {"c": 384})
    cfg = authority.load(camp)
    authority.write(
        CampaignMempalaceConfig(
            campaign=cfg.campaign, recipe_version=cfg.recipe_version, wings=cfg.wings
        ),
        camp,
    )
    runner, calls = _runner()
    res = refresh.refresh(entity, campaign="saga", runner=runner)
    assert res[0].failed and "mneme mp bringup" in res[0].error and _mines(calls) == []


def test_bringup_refuses_mismatch_and_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    root = tmp_path / "campaigns"
    camp = make_greenfield_campaign(root, "stormhaven")
    entity = with_env(entity_for(root), OLLAMA)
    store = authority.store_path_for("stormhaven", None)
    make_store(store, {"c": 384})
    before = sorted(p.relative_to(camp) for p in camp.rglob("*"))
    runner, calls = _runner()
    rep = bringup.bringup(
        entity, "stormhaven", runner=runner, do_backup=False, prober=prober_for(1024)
    )
    assert not rep.ready and _mines(calls) == []
    assert sorted(p.relative_to(camp) for p in camp.rglob("*")) == before  # no authority/faces
    assert not authority.has_authority(camp)


def test_regenerate_succeeds_when_old_dim_differs(tmp_path, monkeypatch):
    entity, store, camp = _setup(tmp_path, monkeypatch, {"c": 384})
    runner, calls = _runner()
    backup.regenerate(entity, "saga", runner=runner, prober=prober_for(1024))
    assert len(_mines(calls)) == 1
    assert not (store / "turbovec").exists()  # old store cleared before the guard ran


def test_regenerate_does_not_delete_when_embedder_down(tmp_path, monkeypatch):
    entity, store, camp = _setup(tmp_path, monkeypatch, {"c": 384})
    runner, calls = _runner()
    with pytest.raises(MempalaceError, match="refusing to clear"):
        backup.regenerate(entity, "saga", runner=runner, prober=prober_for(None))
    assert (store / "turbovec" / "c" / "store.sqlite3").exists() and _mines(calls) == []


# ---- status row ------------------------------------------------------------------------
def _row(entity, prober):
    report = conform.report(entity, campaign="saga", runner=_runner()[0], prober=prober)
    return next(r for r in report.rows if r.dimension == "embedder")


def test_status_embedder_rows_and_exit(tmp_path, monkeypatch):
    entity, store, camp = _setup(tmp_path, monkeypatch, {"c": 1024})
    ok = _row(entity, prober_for(1024))
    assert ok.state is State.CONFORMANT and ok.ok and "1024" in ok.note
    for dim, state in ((768, State.EMBEDDER_MISMATCH), (None, State.EMBEDDER_UNVERIFIED)):
        row = _row(entity, prober_for(dim))
        assert row.state is state and not row.ok
        report = conform.report(
            entity, campaign="saga", runner=_runner()[0], prober=prober_for(dim)
        )
        assert report.exit_code() == 1


def test_status_embedder_row_omitted_when_store_missing_and_no_vectors(tmp_path, monkeypatch):
    entity, store, camp = _setup(tmp_path, monkeypatch, None)
    rows = conform.report(entity, campaign="saga", runner=_runner()[0]).rows
    assert not [r for r in rows if r.dimension == "embedder"]
    (store / "turbovec").mkdir(parents=True)  # dir exists, no vectors
    rows = conform.report(entity, campaign="saga", runner=_runner()[0]).rows
    row = next(r for r in rows if r.dimension == "embedder")
    assert row.ok and "no vectors yet" in row.note
