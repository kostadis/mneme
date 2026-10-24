"""T040: `mneme corpus current` (read-only, from the palace) and `corpus init` (skeleton)."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from mneme.corpus import cli as ccli
from mneme.corpus import config as cconfig
from mneme.mempalace import authority, refresh, render
from mneme.mempalace import recipe as recipe_mod
from mneme.mempalace.runner import MempalaceRunner
from tests.fixtures.corpus_campaign import DECLARED, corpus_world, tree_snapshot

CLI = CliRunner()


def _wire(monkeypatch, w):
    monkeypatch.setattr("mneme.corpus.cli._load_or_exit", lambda _c: w.entity)
    monkeypatch.setattr(MempalaceRunner, "for_entity", classmethod(lambda c, e, **k: w.runner))


def _settle(w):
    cfg = authority.load(w.camp, mempalace_root=w.store.parent.parent)
    render.write_all(cfg, recipe_mod.current(), w.camp)
    (res,) = refresh.refresh(w.entity, campaign="corp", runner=w.runner)
    assert not res.failed, res.error


@pytest.fixture
def w(tmp_path, monkeypatch):
    world = corpus_world(tmp_path, monkeypatch)
    _wire(monkeypatch, world)
    return world


def test_current_lists_files_grouped_by_wing_with_relative_paths(w):
    _settle(w)
    before = (tree_snapshot(w.camp), w.sources())
    res = CLI.invoke(ccli.app, ["current", "corp"])
    assert res.exit_code == 0, res.output
    assert "npcs: 1 file(s)" in res.output and "  docs/npcs/a.md" in res.output
    for rel in DECLARED:
        assert rel in res.output
    assert str(w.camp) not in res.output  # campaign-relative, not absolute
    assert (tree_snapshot(w.camp), w.sources()) == before  # read-only


def test_current_without_a_store_says_no_palace(w):
    res = CLI.invoke(ccli.app, ["current", "corp"])  # authority, but never provisioned
    assert res.exit_code == 0 and "no palace" in res.output


def test_current_without_an_authority_says_no_palace(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch, authority=False)
    _wire(monkeypatch, w)
    res = CLI.invoke(ccli.app, ["current", "corp"])
    assert res.exit_code == 0 and "no palace" in res.output


def test_current_unreadable_palace_is_unknown_never_empty(w, monkeypatch):
    _settle(w)
    monkeypatch.setenv("MNEME_STUB_SOURCES", "rc1")
    res = CLI.invoke(ccli.app, ["current", "corp"])
    assert res.exit_code != 0 and "unknown" in res.output
    assert "holds no files" not in res.output


def test_init_writes_a_skeleton_that_loads_with_no_kinds_declared(w):
    (w.camp / ".mneme" / "corpus.yaml").unlink()
    res = CLI.invoke(ccli.app, ["init", "corp"])
    assert res.exit_code == 0, res.output
    text = (w.camp / ".mneme" / "corpus.yaml").read_text()
    rec = recipe_mod.current()
    assert "campaign: corp" in text
    for k in rec.kinds:
        assert f"#   {k.name}:" in text
    live = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    assert live == ["campaign: corp"]  # no kind, no path: everything else is a comment
    cfg = cconfig.load(w.camp, rec)  # chosen: it loads, declaring an empty corpus
    assert cfg.campaign == "corp" and cfg.kinds == {}


def test_init_refuses_to_overwrite(w):
    path = w.camp / ".mneme" / "corpus.yaml"
    before = path.read_bytes()
    res = CLI.invoke(ccli.app, ["init", "corp"])
    assert res.exit_code != 0 and "already exists" in res.output
    assert path.read_bytes() == before


def test_current_with_a_store_path_that_is_a_file_refuses_naming_it(w):
    w.store.parent.mkdir(parents=True, exist_ok=True)
    w.store.write_text("not a directory")
    res = CLI.invoke(ccli.app, ["current", "corp"])
    assert res.exit_code != 0 and "store path is not a directory" in res.output, res.output
