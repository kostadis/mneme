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
import subprocess
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


def _write(camp: Path, rel: str, text: str) -> Path:
    p = camp / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_doc(rel, text))
    return p


_CORPUS_YAML = """\
campaign: stormhaven
kinds:
  npcs:
    dirs: [docs/npcs]
  grounding:
    files:
      - docs/world_state.md
      - docs/party.md
      - docs/current_state.md   # a symlink to a regular file inside the campaign
  party:
    files: [docs/party.md]
    mined_as: true
"""


def test_real_mempalace_declared_corpus(tmp_path, monkeypatch):
    """Feature 007 R1-R4 against the real binary: `mine --files-from`, `sources --json`,
    `forget --sources-from`, driven through mneme's corpus bring-up/status/refresh/prune."""
    home = tmp_path / "home"
    home.mkdir()
    for var in [k for k in os.environ if k.startswith(("MEMPALACE_", "GIT_"))]:
        monkeypatch.delenv(var)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(embedder_guard, "default_prober", _REAL_PROBER)

    root = tmp_path / "campaigns"
    camp = root / "stormhaven"
    declared = {
        "docs/npcs/mira.md": "npcs",
        "docs/npcs/guild/torv.md": "npcs",
        "docs/world_state.md": "grounding",
        "docs/party.md": "party",  # declared as party AND grounding; mined once, as party
        "docs/grounding/gen1/current_state.md": "grounding",  # the symlink's target
    }
    for rel in declared:
        _write(camp, rel, f"canon of {rel}.")
    _write(camp, "docs/grounding/gen2/current_state.md", "the second generation.")
    # undeclared files that must never be mined
    _write(camp, "docs/world_state_draft.md", "a draft.")
    _write(camp, "notes/ideas.md", "loose notes.")
    link = camp / "docs" / "current_state.md"
    link.symlink_to("grounding/gen1/current_state.md")
    (camp / ".mneme").mkdir()
    (camp / ".mneme" / "corpus.yaml").write_text(_CORPUS_YAML)
    subprocess.run(["git", "init", "-q"], cwd=camp, check=True)

    entity = dataclasses.replace(
        entity_for(root),
        venv=Path(_VENV).expanduser(),
        env={"MEMPALACE_BACKEND": "turbovec", "MEMPALACE_EMBEDDING_PROVIDER": "onnx"},
    )
    runner = MempalaceRunner.for_entity(entity)
    store = home / ".mempalace" / "palaces" / "stormhaven"
    camp_real = camp.resolve()

    def held() -> dict[str, tuple[str, int]]:
        recs = runner.sources(palace=store)
        assert recs is not None, "real `sources --json` did not parse"
        return {str(Path(r.source_file).relative_to(camp_real)): (r.wing, r.drawers) for r in recs}

    def corpus_row():
        return _rows(entity, "stormhaven", runner)["corpus"]

    # --- the real binary advertises the corpus verbs ---------------------------------------
    assert runner.supports_corpus() is True

    # --- bring-up from corpus.yaml alone (no authority file): real `mine --files-from` -----
    report = bringup.bringup(entity, "stormhaven", runner=runner, do_backup=False)
    assert report.ready, [(s.name, s.state, s.note) for s in report.steps]
    # the rendered root mempalace.yaml (palace + rooms, no `wing:`) was accepted by the binary
    root_yaml = (camp / "mempalace.yaml").read_text()
    assert "wing:" not in root_yaml.replace("wings:", "")

    # --- sources: exactly the declared files, wing per kind, symlink recorded as its target -
    got = held()
    expected = dict(declared)
    assert {k: v[0] for k, v in got.items()} == expected, got
    assert all(n >= 1 for _, n in got.values())
    assert "docs/current_state.md" not in got  # the symlink path itself is never a source
    assert not {"docs/world_state_draft.md", "notes/ideas.md"} & set(got)
    assert got["docs/party.md"][0] == "party"  # not grounding

    # --- status: the corpus row is clean ---------------------------------------------------
    row = corpus_row()
    assert row.state is State.CONFORMANT, row

    # --- a new file under a declared dir: unmined -> refresh -> clean ----------------------
    _write(camp, "docs/npcs/guild/sela.md", "a new guild member.")
    row = corpus_row()
    assert row.state is State.UNMINED and "docs/npcs/guild/sela.md" in row.note, row
    (res,) = refresh.refresh(entity, "stormhaven", runner=runner, prober=_REAL_PROBER)
    assert not res.failed, res.error
    assert corpus_row().state is State.CONFORMANT
    assert held()["docs/npcs/guild/sela.md"][0] == "npcs"

    # --- a content change: stale -> refresh -> clean (hash-driven; drawers re-mined) -------
    (camp / "docs" / "world_state.md").write_text(_doc("World", "Stormhaven fell to the raiders."))
    row = corpus_row()
    assert row.state is State.CORPUS_STALE and "docs/world_state.md" in row.note, row
    (res,) = refresh.refresh(entity, "stormhaven", runner=runner, prober=_REAL_PROBER)
    assert not res.failed, res.error
    assert corpus_row().state is State.CONFORMANT
    assert held()["docs/world_state.md"][1] >= 1

    # --- undeclare a file: undeclared-drawers -> prune preview -> --confirm --expect N -----
    monkeypatch.setattr(cli, "_load_or_exit", lambda config: entity)
    monkeypatch.setattr(MempalaceRunner, "for_entity", classmethod(lambda c, e, **k: runner))
    cy = camp / ".mneme" / "corpus.yaml"
    cy.write_text(_CORPUS_YAML.replace("dirs: [docs/npcs]", "dirs: [docs/npcs/guild]"))
    cli_runner = CliRunner()
    rn = cli_runner.invoke(cli.app, ["render", "stormhaven"])  # TOC stamp follows the edit
    assert rn.exit_code == 0, rn.output
    row = corpus_row()
    assert row.state is State.UNDECLARED_DRAWERS and "docs/npcs/mira.md" in row.note, row
    before = held()
    n = before["docs/npcs/mira.md"][1]
    pv = cli_runner.invoke(cli.app, ["prune", "stormhaven"])
    print(pv.output)
    assert pv.exit_code == 0 and "docs/npcs/mira.md" in pv.output
    assert f"--confirm --expect {n}" in pv.output
    assert held() == before  # a preview deletes nothing
    pc = cli_runner.invoke(
        cli.app, ["prune", "stormhaven", "--confirm", "--expect", str(n),
                  "--include-former-canon", "npcs"],
    )
    print(pc.output)
    assert pc.exit_code == 0, pc.output
    assert "backed up" in pc.output and "verified" in pc.output
    after = held()
    assert "docs/npcs/mira.md" not in after
    assert after == {k: v for k, v in before.items() if k != "docs/npcs/mira.md"}
    assert corpus_row().state is State.CONFORMANT

    # --- re-point the symlink: refresh replaces the old target's drawers (no prune) --------
    link.unlink()
    link.symlink_to("grounding/gen2/current_state.md")
    (res,) = refresh.refresh(entity, "stormhaven", runner=runner, prober=_REAL_PROBER)
    assert not res.failed, res.error
    assert "replaced 1 re-pointed files" in res.line(), res.line()
    final = held()
    assert "docs/grounding/gen1/current_state.md" not in final
    assert final["docs/grounding/gen2/current_state.md"][0] == "grounding"
    assert corpus_row().state is State.CONFORMANT
