"""GH #34 — restore refuses embedder-mismatched backups and verifies freshness afterwards."""

from __future__ import annotations

import shutil

import pytest
from typer.testing import CliRunner

from mneme.mempalace import backup, bringup, cli
from mneme.mempalace.models import State
from mneme.mempalace.runner import MempalaceRunner
from tests.fixtures import STUB, entity_for, make_greenfield_campaign
from tests.unit.test_mp_embedder_guard import make_store, prober_for


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("MNEME_STUB_LOG", str(tmp_path / "stub.log"))
    runner = MempalaceRunner(binary=str(STUB))
    root = tmp_path / "campaigns"
    make_greenfield_campaign(root, "stormhaven")
    entity = entity_for(root)
    bringup.bringup(entity, "stormhaven", runner=runner, do_backup=True)
    store = tmp_path / "home" / ".mempalace" / "palaces" / "stormhaven"
    shutil.rmtree(store)
    return entity, store, runner


def test_mismatched_backup_refused_store_untouched(world):
    entity, store, runner = world
    snap = backup.latest_backup(entity, "stormhaven")
    for coll in ("mempalace_drawers", "mempalace_closets"):
        (snap / "turbovec" / coll / "store.sqlite3").unlink()
    make_store(snap, {"mempalace_drawers": 1024, "mempalace_closets": 1024})
    with pytest.raises(backup.BackupError, match=r"dim 1024.*dim 384.*regenerate"):
        backup.restore(entity, "stormhaven", runner=runner, prober=prober_for(384))
    assert not store.exists()


def test_unknown_probe_proceeds_but_not_fresh(world):
    entity, store, runner = world
    res = backup.restore(entity, "stormhaven", runner=runner, prober=prober_for(None))
    assert res.restored and store.exists()
    assert not res.fresh
    assert any(r.state is State.EMBEDDER_UNVERIFIED for r in res.rows)


def test_clean_restore_is_fresh(world):
    entity, _store, runner = world
    res = backup.restore(entity, "stormhaven", runner=runner, prober=prober_for(384))
    assert res.fresh, [r for r in res.rows]
    assert {"recipe", "render", "embedder", "index"} <= {r.dimension for r in res.rows}


def test_stale_index_not_fresh(world, monkeypatch):
    entity, _store, runner = world
    monkeypatch.setenv("MNEME_STUB_SYNC", "3,0,0")
    res = backup.restore(entity, "stormhaven", runner=runner, prober=prober_for(384))
    assert not res.fresh
    assert any(r.state is State.STALE for r in res.rows)


def _invoke(entity, runner, monkeypatch):
    monkeypatch.setattr(cli, "_load_or_exit", lambda config: entity)
    monkeypatch.setattr(MempalaceRunner, "for_entity", classmethod(lambda c, e, **k: runner))
    return CliRunner().invoke(cli.app, ["restore", "stormhaven"])


def test_cli_clean_exit_zero(world, monkeypatch):
    entity, _s, runner = world
    res = _invoke(entity, runner, monkeypatch)
    assert res.exit_code == 0, res.output
    assert "restore verified" in res.output
    assert "mneme mp refresh stormhaven" in res.output


def test_cli_stale_nonzero_recommends_prune(world, monkeypatch):
    entity, _s, runner = world
    monkeypatch.setenv("MNEME_STUB_SYNC", "3,0,0")
    res = _invoke(entity, runner, monkeypatch)
    assert res.exit_code != 0
    assert "NOT fresh" in res.output
    assert "recommend: `mneme mp prune stormhaven`" in res.output
    assert "recommend: `mneme mp refresh" not in res.output


def test_cli_out_of_scope_recommends_regenerate_and_both(world, monkeypatch):
    entity, _s, runner = world
    monkeypatch.setenv("MNEME_STUB_SYNC", "0,0,4")
    res = _invoke(entity, runner, monkeypatch)
    assert "mneme mp regenerate stormhaven --confirm" in res.output
    assert "mneme mp prune" not in res.output
    monkeypatch.setenv("MNEME_STUB_SYNC", "2,0,4")
    res = _invoke(entity, runner, monkeypatch)
    assert "mneme mp regenerate stormhaven --confirm" in res.output
    assert "mneme mp prune stormhaven" in res.output



def test_incoherent_backup_refused(world):
    entity, store, runner = world
    snap = backup.latest_backup(entity, "stormhaven")
    (snap / "turbovec" / "mempalace_closets" / "store.sqlite3").unlink()
    make_store(snap, {"mempalace_closets": 1024})
    with pytest.raises(backup.BackupError, match="incoherent"):
        backup.restore(entity, "stormhaven", runner=runner, prober=prober_for(384))
    assert not store.exists()


def test_restore_replaces_store_and_keeps_aside(world):
    entity, store, runner = world
    (store / "turbovec" / "leftover").mkdir(parents=True)
    (store / "turbovec" / "leftover" / "store.sqlite3").write_text("x")
    (store / "turbovec" / "mempalace_drawers").mkdir(parents=True, exist_ok=True)
    (store / "turbovec" / "mempalace_drawers" / "index.tvim").write_text("stale")
    res = backup.restore(entity, "stormhaven", runner=runner, prober=prober_for(384))
    assert not (store / "turbovec" / "leftover").exists()
    assert not (store / "turbovec" / "mempalace_drawers" / "index.tvim").exists()
    assert res.previous_store and res.previous_store.is_dir()
    assert (res.previous_store / "turbovec" / "leftover").is_dir()


def test_symlinked_store_keeps_link_and_moves_target_aside(world, tmp_path):
    entity, store, runner = world
    real = tmp_path / "bigdisk" / "stormhaven-real"
    (real / "turbovec" / "leftover").mkdir(parents=True)
    (real / "turbovec" / "leftover" / "store.sqlite3").write_text("x")
    store.parent.mkdir(parents=True, exist_ok=True)
    store.symlink_to(real, target_is_directory=True)
    res = backup.restore(entity, "stormhaven", runner=runner, prober=prober_for(384))
    assert store.is_symlink() and store.resolve() == real.resolve()
    assert not (real / "turbovec" / "leftover").exists()
    assert (store / "turbovec").is_dir()  # restored data visible through the link
    assert res.previous_store == real.with_name(res.previous_store.name)
    assert not res.previous_store.is_symlink()
    assert (res.previous_store / "turbovec" / "leftover").is_dir()
    assert not list(store.parent.glob("*.pre-restore-*"))  # nothing aside next to the link


def test_symlinked_store_failed_copy_rolls_back_target(world, monkeypatch, tmp_path):
    entity, store, runner = world
    real = tmp_path / "bigdisk" / "real"
    real.mkdir(parents=True)
    (real / "marker").write_text("orig")
    store.parent.mkdir(parents=True, exist_ok=True)
    store.symlink_to(real, target_is_directory=True)

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(backup.shutil, "copy2", boom)
    with pytest.raises(OSError):
        backup.restore(entity, "stormhaven", runner=runner, prober=prober_for(384))
    assert store.is_symlink()
    assert (real / "marker").read_text() == "orig"
    assert not list(real.parent.glob("*.pre-restore-*"))


def test_failed_copy_rolls_back(world, monkeypatch):
    entity, store, runner = world
    store.mkdir(parents=True)
    (store / "marker").write_text("orig")

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(backup.shutil, "copy2", boom)
    with pytest.raises(OSError):
        backup.restore(entity, "stormhaven", runner=runner, prober=prober_for(384))
    assert (store / "marker").read_text() == "orig"
    assert not list(store.parent.glob("*.pre-restore-*"))
    assert not (store / "turbovec").exists()


def test_campaign_dir_name_differs_from_arg(world, tmp_path):
    entity, _store, runner = world
    src = tmp_path / "campaigns" / "stormhaven"
    other = tmp_path / "campaigns" / "elsewhere"
    src.rename(other)
    res = backup.restore(
        entity, "stormhaven", campaign_dir=str(other), runner=runner, prober=prober_for(384)
    )
    assert res.rows and not res.missing
    assert {r.dimension for r in res.rows} >= {"recipe", "render", "embedder", "index", "store"}


@pytest.mark.parametrize("cmd", ["restore", "regenerate"])
@pytest.mark.parametrize("kind", ["discovery", "authority", "oserror", "mempalace"])
def test_cli_catches_runtime_errors_without_traceback(world, monkeypatch, cmd, kind):
    from mneme.mempalace import discover
    from mneme.mempalace.authority import AuthorityError
    from mneme.mempalace.runner import MempalaceError

    entity, _store, _runner = world
    monkeypatch.setattr(cli, "_load_or_exit", lambda config: entity)
    exc = {
        "discovery": discover.DiscoveryError("no such campaign"),
        "authority": AuthorityError(["no store pointer"]),
        "oserror": OSError("rename failed"),
        "mempalace": MempalaceError("boom"),
    }[kind]

    def raiser(*a, **k):
        raise exc

    monkeypatch.setattr(backup, cmd, raiser)
    args = [cmd, "stormhaven"] + (["--confirm"] if cmd == "regenerate" else [])
    res = CliRunner().invoke(cli.app, args)
    assert res.exit_code == cli.EXIT_RUNTIME, res.output
    assert f"FAIL {cmd}:" in res.output
    assert isinstance(res.exception, SystemExit)  # a clean exit, not an escaped traceback
    if kind == "authority":
        assert "no store pointer" in res.output and "invalid .mneme" not in res.output


def test_cli_restore_real_discovery_error(world, monkeypatch):
    entity, _store, _runner = world
    monkeypatch.setattr(cli, "_load_or_exit", lambda config: entity)
    res = CliRunner().invoke(cli.app, ["restore", "nonexistent"])
    assert res.exit_code == cli.EXIT_RUNTIME and "FAIL restore:" in res.output
