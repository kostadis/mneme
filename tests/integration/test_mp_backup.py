"""US3 integration (T019): backup → delete store → restore preserves bindings, no re-embed."""

from __future__ import annotations

import shutil

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
