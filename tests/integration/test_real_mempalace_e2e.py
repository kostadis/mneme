"""Real-binary e2e: mneme's mp flow against an ACTUAL installed `mempalace` (turbovec + onnx).

Every other mp test drives ``tests/fixtures/stub_mempalace.py``, so a parser written against
a fictional output format passes (GH #22: the `sync` report). This test closes that gap: it
runs bring-up -> status -> orphan detection -> refresh -> prune -> backup/restore -> regenerate with
the real binary, a sandboxed HOME, and the real subprocess embedder probe.

Opt-in: set ``MNEME_REAL_MEMPALACE_VENV`` to a venv with mempalace + turbovecdb installed
(e.g. one built by ``hypostasis install``). Skips cleanly otherwise. onnx may download a
small model on first use.
"""

from __future__ import annotations

import dataclasses
import os
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mneme.mempalace import backup, bringup, cli, conform, embedder_guard, refresh
from mneme.mempalace.models import State
from mneme.mempalace.runner import MempalaceRunner
from tests.fixtures import entity_for

# Captured at import (collection) time: conftest's autouse fixture later replaces
# embedder_guard.default_prober with a stub; this test needs the real subprocess probe.
_REAL_PROBER = embedder_guard.default_prober

_VENV = os.environ.get("MNEME_REAL_MEMPALACE_VENV", "")
_BIN = Path(_VENV).expanduser() / "bin" / "mempalace" if _VENV else None

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        _BIN is None or not _BIN.exists(),
        reason="set MNEME_REAL_MEMPALACE_VENV to a venv with a real mempalace to run",
    ),
]

_BODY = "The party gathers at the Stormhaven docks and discusses the goblin raids at length. "


def _doc(title: str, tail: str) -> str:
    return f"# {title}\n{_BODY * 6}\n{tail}\n"  # > mempalace's 50-char minimum chunk


def _rows(entity, campaign, runner):
    rep = conform.report(entity, campaign, runner=runner, prober=_REAL_PROBER)
    return {r.dimension: r for r in rep.rows}


def test_real_mempalace_end_to_end(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    # Hermetic: no shell MEMPALACE_* (CONFIG_DIR, PALACE_PATH, EMBEDDING_*, ...) may steer the
    # real binary at a real palace; only the entity env below is passed on. GIT_* likewise.
    for var in [k for k in os.environ if k.startswith(("MEMPALACE_", "GIT_"))]:
        monkeypatch.delenv(var)
    monkeypatch.setenv("HOME", str(home))  # mempalace reads ~/.mempalace/config.json
    monkeypatch.setattr(embedder_guard, "default_prober", _REAL_PROBER)

    root = tmp_path / "campaigns"
    camp = root / "stormhaven"
    (camp / "docs" / "chapters").mkdir(parents=True)
    chapters = camp / "docs" / "chapters"
    (chapters / "chapter_01.md").write_text(_doc("Chapter 1", "The vault opens."))
    (chapters / "chapter_02.md").write_text(_doc("Chapter 2", "Daz forges a key."))
    (camp / "world.md").write_text(_doc("World", "Stormhaven stands on the cliffs."))
    (camp / "notes.md").write_text(_doc("Notes", "A delete-me note about goblins."))

    entity = dataclasses.replace(
        entity_for(root),
        venv=Path(_VENV).expanduser(),
        env={"MEMPALACE_BACKEND": "turbovec", "MEMPALACE_EMBEDDING_PROVIDER": "onnx"},
    )
    runner = MempalaceRunner.for_entity(entity)
    assert runner.binary == str(_BIN)

    # --- bring-up: configure, faces, provision, first mine (real `mempalace mine`) ---------
    report = bringup.bringup(entity, "stormhaven", runner=runner, do_backup=False)
    assert report.ready, [(s.name, s.state, s.note) for s in report.steps]
    store = home / ".mempalace" / "palaces" / "stormhaven"
    assert (store / "turbovec" / "mempalace_drawers" / "store.sqlite3").exists()

    # --- status: every row parses the REAL output (no UNVERIFIED from a parse failure) ------
    rows = _rows(entity, "stormhaven", runner)
    assert rows["index"].state is State.BUILT, rows["index"]
    assert "no orphaned drawers" in rows["index"].note
    assert rows["store"].state is State.BUILT, rows["store"]
    assert rows["embedder"].state is State.CONFORMANT, rows["embedder"]
    assert "dim 384" in rows["embedder"].note  # onnx all-MiniLM-L6-v2, probed in a subprocess

    # --- orphan: delete a mined source; real `sync --dry-run` reports `Missing: 1` ---------
    (camp / "notes.md").unlink()
    idx = _rows(entity, "stormhaven", runner)["index"]
    assert idx.state is State.STALE, idx
    assert "1 orphaned drawers" in idx.note and "1 missing" in idx.note

    # --- refresh succeeds against the real `mine` CLI flags --------------------------------
    results = refresh.refresh(entity, "stormhaven", runner=runner, prober=_REAL_PROBER)
    assert len(results) == 1 and not results[0].failed and not results[0].skipped
    # ...and cannot clear the orphan: it only mines
    assert _rows(entity, "stormhaven", runner)["index"].state is State.STALE

    # --- prune: preview (real dry-run), then --confirm (real `sync --apply --root`) --------
    monkeypatch.setattr(cli, "_load_or_exit", lambda config: entity)
    monkeypatch.setattr(MempalaceRunner, "for_entity", classmethod(lambda c, e, **k: runner))
    cli_runner = CliRunner()
    pv = cli_runner.invoke(cli.app, ["prune", "stormhaven"])
    print(pv.output)
    assert pv.exit_code == 0 and "would remove 1 orphaned drawers (1 missing" in pv.output
    assert "--confirm --expect 1" in pv.output
    pc = cli_runner.invoke(cli.app, ["prune", "stormhaven", "--confirm", "--expect", "1"])
    print(pc.output)
    assert pc.exit_code == 0, pc.output
    assert "backed up bindings" in pc.output and "verified" in pc.output
    idx = _rows(entity, "stormhaven", runner)["index"]
    assert idx.state is State.BUILT, idx
    assert "no orphaned drawers" in idx.note

    # --- backup + restore (into a deleted store): freshness rows sensible ------------------
    snap = backup.backup(entity, "stormhaven")
    assert any(p.name == "store.sqlite3" for p in snap.contents)
    shutil.rmtree(store)
    restored = backup.restore(entity, "stormhaven", runner=runner, prober=_REAL_PROBER)
    assert restored.restored and not restored.missing
    by_dim = {r.dimension: r for r in restored.rows}
    assert by_dim["store"].state is State.BUILT
    assert by_dim["embedder"].state is State.CONFORMANT

    # --- regenerate: the only re-embed path; ends coherent with the orphan gone ------------
    backup.regenerate(entity, "stormhaven", runner=runner, prober=_REAL_PROBER)
    rows = _rows(entity, "stormhaven", runner)
    assert rows["index"].state is State.BUILT, rows["index"]
    assert rows["embedder"].state is State.CONFORMANT, rows["embedder"]
