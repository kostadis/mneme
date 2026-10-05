"""US3 integration (T019): backup → delete store → restore preserves bindings, no re-embed."""

from __future__ import annotations

import os
import shutil

import pytest

from mneme.mempalace import backup, bringup
from mneme.mempalace.runner import MempalaceRunner
from tests.fixtures import STUB, entity_for, make_greenfield_campaign


def test_backup_restore_no_reembed(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    log = tmp_path / "stub.log"
    monkeypatch.setenv("MNEME_STUB_LOG", str(log))
    runner = MempalaceRunner(binary=str(STUB))
    root = tmp_path / "campaigns"
    make_greenfield_campaign(root, "stormhaven")
    entity = entity_for(root)
    bringup.bringup(entity, "stormhaven", runner=runner, do_backup=True)

    store = tmp_path / "home" / ".mempalace" / "palaces" / "stormhaven"
    assert (store / "turbovec" / "mempalace_drawers" / "store.sqlite3").exists()

    shutil.rmtree(store)  # lose the store
    mines_before = log.read_text().count("mine ")
    backup.restore(entity, "stormhaven")

    # bindings are back and restore invoked NO mine (no re-embed) — turbovecdb rebuilds the index
    assert (store / "turbovec" / "mempalace_drawers" / "store.sqlite3").exists()
    assert log.read_text().count("mine ") == mines_before


def test_backup_captures_rows_still_in_the_wal(tmp_path, monkeypatch):
    """Real turbovecdb stores run in WAL mode: right after a mine, committed rows can sit in
    `store.sqlite3-wal`. A bare file copy of the main DB would snapshot an EMPTY store (found
    against the real mempalace); the backup must capture them."""
    import sqlite3

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    root = tmp_path / "campaigns"
    make_greenfield_campaign(root, "stormhaven")
    entity = entity_for(root)
    monkeypatch.setenv("MNEME_STUB_LOG", str(tmp_path / "stub.log"))
    bringup.bringup(
        entity, "stormhaven", runner=MempalaceRunner(binary=str(STUB)), do_backup=False
    )
    store = tmp_path / "home" / ".mempalace" / "palaces" / "stormhaven"
    coll = store / "turbovec" / "mempalace_drawers"
    (coll / "store.sqlite3").unlink()
    live = sqlite3.connect(coll / "store.sqlite3")  # held open: no checkpoint on close
    live.execute("PRAGMA journal_mode=WAL")
    live.execute("PRAGMA wal_autocheckpoint=0")
    live.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    live.execute("INSERT INTO meta VALUES ('dim', '384')")
    live.commit()
    assert (coll / "store.sqlite3-wal").stat().st_size > 0  # the row is only in the WAL

    snap = backup.backup(entity, "stormhaven")
    live.close()

    copy = sqlite3.connect(snap.location / "turbovec" / "mempalace_drawers" / "store.sqlite3")
    try:
        assert copy.execute("SELECT value FROM meta WHERE key='dim'").fetchone() == ("384",)
    finally:
        copy.close()


def _wal_db(path, dim="384"):
    """A WAL-mode SQLite db, held open with autocheckpoint off so its rows live only in -wal."""
    import sqlite3

    path.parent.mkdir(parents=True, exist_ok=True)
    live = sqlite3.connect(path)
    live.execute("PRAGMA journal_mode=WAL")
    live.execute("PRAGMA wal_autocheckpoint=0")
    live.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    live.execute("INSERT INTO meta VALUES ('dim', ?)", (dim,))
    live.commit()
    return live


def _dim(path):
    import sqlite3

    con = sqlite3.connect(path)
    try:
        return con.execute("SELECT value FROM meta WHERE key='dim'").fetchone()
    finally:
        con.close()


@pytest.mark.parametrize("dirname", ["a?b", "c#d", "e%20f"])
def test_snapshot_handles_uri_special_chars_in_path(tmp_path, dirname):
    src = tmp_path / dirname / "store.sqlite3"
    live = _wal_db(src)
    dest = tmp_path / "out" / "store.sqlite3"
    dest.parent.mkdir()
    backup._snapshot_file(src, dest)
    live.close()
    assert _dim(dest) == ("384",)
    # no stray database was created by a truncated URI (`?`/`#` cut the path short)
    stray = [p.name for p in tmp_path.iterdir() if p.name not in (dirname, "out")]
    assert stray == []


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_snapshot_readonly_store_dir_keeps_wal_rows(tmp_path):
    live_dir = tmp_path / "live"
    live = _wal_db(live_dir / "store.sqlite3")
    coll = tmp_path / "coll"  # crash leftovers: db + -wal with committed rows, no -shm
    coll.mkdir()
    shutil.copy2(live_dir / "store.sqlite3", coll / "store.sqlite3")
    shutil.copy2(live_dir / "store.sqlite3-wal", coll / "store.sqlite3-wal")
    live.close()
    src = coll / "store.sqlite3"
    assert (coll / "store.sqlite3-wal").stat().st_size > 0
    dest = tmp_path / "out" / "store.sqlite3"
    dest.parent.mkdir()
    coll.chmod(0o555)
    try:
        backup._snapshot_file(src, dest)
    finally:
        coll.chmod(0o755)
    assert _dim(dest) == ("384",)
