"""Quickstart scenario 4 (US4, T043): an existing wing-model campaign moves to a declared
corpus deliberately — owed, listed, never deleted before a confirmed prune."""

from __future__ import annotations

import pytest
import yaml
from typer.testing import CliRunner

from mneme.corpus import cli as ccli
from mneme.mempalace import authority, conform, render
from mneme.mempalace import recipe as recipe_mod
from mneme.mempalace.models import FAIL_STATES, ConformanceReport, State
from mneme.mempalace.runner import MempalaceRunner
from tests.fixtures.corpus_campaign import CORPUS_YAML, corpus_world

WING_AUTHORITY = """\
campaign: corp
recipe_version: "3.0.0"
store:
  alias: corp
wings:
  - name: reviews
    source: docs/reviews
    trust: reference
    rooms:
      - {name: general, description: Reviews, keywords: []}
  - name: corp
    source: .
    trust: reference
    rooms:
      - {name: general, description: Top-level docs, keywords: []}
extra_exclusions:
  - scratch/
"""

TODAY = {"corp": ["docs/world_state.md", "docs/npcs/a.md"], "reviews": ["docs/reviews/x.md"]}


def _rows(w):
    rep = conform.report(w.entity, "corp", runner=w.runner)
    return {r.dimension: r for r in rep.rows}, rep


def _cfg(w):
    return authority.load(w.camp, mempalace_root=w.store.parent.parent)


@pytest.fixture
def w(tmp_path, monkeypatch):
    world = corpus_world(tmp_path, monkeypatch)
    (world.camp / ".mneme" / "corpus.yaml").unlink()  # still the wing model
    (world.camp / ".mneme" / "mempalace.yaml").write_text(WING_AUTHORITY)
    world.store.mkdir(parents=True)
    for wing, files in TODAY.items():  # the palace as the wing model left it
        world.runner.mine_files(world.camp, files, wing=wing, palace=world.store)
    monkeypatch.setattr("mneme.corpus.cli._load_or_exit", lambda _c: world.entity)
    monkeypatch.setattr(MempalaceRunner, "for_entity", classmethod(lambda c, e, **k: world.runner))
    return world


def test_wing_model_to_declared_corpus(w):
    # 1. owed, listed, not a failure; wing-model mining is untouched.
    rows, rep = _rows(w)
    assert rows["corpus"].state is State.CORPUS_UNDECLARED
    assert "mneme corpus init corp" in rows["corpus"].note
    assert rows["corpus"].state not in FAIL_STATES
    mine = ConformanceReport(tuple(r for r in rep.rows if r.dimension == "corpus"))
    assert mine.exit_code() == 0 and mine.exit_code(strict=True) == 0

    # 2. `corpus current` lists today's files, grouped by wing, and changes nothing.
    held = w.sources()
    res = CliRunner().invoke(ccli.app, ["current", "corp"])
    assert res.exit_code == 0, res.output
    assert "corp: 2 file(s)" in res.output and "reviews: 1 file(s)" in res.output
    for rel in ("docs/world_state.md", "docs/npcs/a.md", "docs/reviews/x.md"):
        assert f"  {rel}" in res.output
    assert w.sources() == held

    # 3. The GM declares a corpus and drops the wing keys; render; status shows the
    #    leftovers as undeclared-drawers — and nothing was deleted.
    (w.camp / ".mneme" / "corpus.yaml").write_text(CORPUS_YAML)
    doc = yaml.safe_load((w.camp / ".mneme" / "mempalace.yaml").read_text())
    for key in ("wings", "extra_exclusions"):
        doc.pop(key)
    (w.camp / ".mneme" / "mempalace.yaml").write_text(yaml.safe_dump(doc, sort_keys=False))
    render.write_all(_cfg(w), recipe_mod.current(), w.camp)

    rows, _ = _rows(w)
    row = rows["corpus"]
    assert row.state is not State.CORPUS_UNDECLARED
    assert "undeclared-drawers" in row.observed and "docs/reviews/x.md" in row.note
    assert w.sources() == held  # no deletion before a confirmed prune
