"""Quickstart scenario 4 (US3, T037): every consumer reads the same file list, resolved fresh
from `corpus.yaml` on every call, never from the snapshot (FR-012/013/021, SC-008)."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from mneme.cli import app
from mneme.corpus import toc as toc_mod
from mneme.mcp import server
from mneme.mempalace import authority, conform, refresh, render
from mneme.mempalace import recipe as recipe_mod
from mneme.mempalace.discover import DiscoveryError
from mneme.mempalace.models import State
from tests.fixtures.corpus_campaign import DECLARED, corpus_world, write

CLI = CliRunner()


@pytest.fixture
def w(tmp_path, monkeypatch):
    world = corpus_world(tmp_path, monkeypatch)
    cfg = authority.load(world.camp, mempalace_root=world.store.parent.parent)
    render.write_all(cfg, recipe_mod.current(), world.camp)
    (res,) = refresh.refresh(world.entity, campaign="corp", runner=world.runner)
    assert not res.failed, res.error
    # CLI commands load hypostasis.yaml; serve the world's entity instead.
    monkeypatch.setattr("mneme.mempalace.cli._load_or_exit", lambda _c: world.entity)
    monkeypatch.setattr("mneme.corpus.cli._load_or_exit", lambda _c: world.entity)
    return world


def cli_toc(*args):
    return CLI.invoke(app, ["corpus", "toc", "corp", *args])


def cli_paths(kind):
    r = cli_toc("--kind", kind, "--json")
    assert r.exit_code == 0, r.output
    return [f["path"] for f in json.loads(r.stdout)["kinds"][kind]["files"]]


def mcp_paths(w, kind):
    out = server.corpus_files(w.entity, "corp", kind)
    assert "error" not in out, out
    return [f["path"] for f in out["files"]]


def corpus_row(w):
    rep = conform.report(w.entity, "corp", runner=w.runner)
    return next(r for r in rep.rows if r.dimension == "corpus")


def test_both_readers_return_identical_lists(w):
    for kind in ("npcs", "summaries", "grounding", "party"):
        assert cli_paths(kind) == mcp_paths(w, kind)
    assert cli_paths("grounding") == sorted(
        ["docs/world_state.md", "docs/campaign_state.md", "docs/party.md", "docs/planning.md"]
    )
    # the CLI document is the full contract shape, restricted to the kind
    doc = json.loads(cli_toc("--kind", "npcs", "--json").stdout)
    assert doc["schema"] == 1 and doc["valid"] is True and list(doc["kinds"]) == ["npcs"]


def test_a_new_file_appears_in_both_with_no_render(w):
    write(w.camp, "docs/npcs/b.md")
    assert "docs/npcs/b.md" in cli_paths("npcs")
    assert "docs/npcs/b.md" in mcp_paths(w, "npcs")


def test_a_hand_edited_snapshot_affects_neither_reader(w):
    before = (cli_paths("npcs"), mcp_paths(w, "npcs"))
    snap = toc_mod.toc_path(w.camp)
    doc = json.loads(snap.read_text())
    doc["kinds"]["npcs"]["files"] = [{"path": "docs/forged.md"}]
    snap.write_text(json.dumps(doc))
    assert (cli_paths("npcs"), mcp_paths(w, "npcs")) == before
    assert "docs/forged.md" not in before[0]
    row = corpus_row(w)
    assert row.state is State.TOC_STALE, row.note


def test_an_invalid_corpus_is_refused_by_both(w):
    p = w.camp / ".mneme" / "corpus.yaml"
    p.write_text(p.read_text() + "bogus_key: 1\n")
    r = cli_toc("--kind", "npcs", "--json")
    assert r.exit_code != 0 and "unknown-key" in r.output
    out = server.corpus_files(w.entity, "corp", "npcs")
    assert out["error"] == "invalid" and "files" not in out and "unknown-key" in out["detail"]


def test_an_undeclared_kind_is_not_declared_not_empty(w):
    r = cli_toc("--kind", "prep", "--json")
    assert r.exit_code != 0 and "kind 'prep' is not declared for this campaign" in r.output
    out = server.corpus_files(w.entity, "corp", "prep")
    assert out["error"] == "not-declared" and "files" not in out


def test_a_declared_empty_kind_is_an_empty_list(w):
    (w.camp / "docs" / "npcs" / "a.md").unlink()
    r = cli_toc("--kind", "npcs", "--json")
    assert r.exit_code == 0
    assert json.loads(r.stdout)["kinds"]["npcs"]["files"] == []
    assert server.corpus_files(w.entity, "corp", "npcs")["files"] == []


def test_write_refreshes_the_snapshot(w):
    write(w.camp, "docs/npcs/b.md")
    assert cli_toc("--write").exit_code == 0
    snap = json.loads(toc_mod.toc_path(w.camp).read_text())
    assert "docs/npcs/b.md" in [f["path"] for f in snap["kinds"]["npcs"]["files"]]


def test_unknown_campaign_propagates(w):
    with pytest.raises(DiscoveryError):
        server.corpus_files(w.entity, "nope", "npcs")


def test_check_exit_codes(w):
    assert CLI.invoke(app, ["corpus", "check", "corp"]).exit_code == 0
    p = w.camp / ".mneme" / "corpus.yaml"
    p.write_text(p.read_text() + "bogus_key: 1\n")
    assert CLI.invoke(app, ["corpus", "check", "corp"]).exit_code != 0
    assert set(DECLARED)  # fixture sanity


def test_a_campaign_on_a_recipe_without_kinds_is_invalid_for_every_reader(w):
    """007 B1: readers resolve with the AUTHORITY's recipe, like mining/status do; a recipe
    that defines no kinds cannot validate a corpus, so `corpus check` must not pass."""
    auth = w.camp / ".mneme" / "mempalace.yaml"
    auth.write_text(auth.read_text().replace('"4.0.0"', '"2.0.0"'))
    r = CLI.invoke(app, ["corpus", "check", "corp"])
    assert r.exit_code != 0 and "defines no kinds" in r.output
    r = cli_toc("--kind", "npcs", "--json")
    assert r.exit_code != 0
    out = server.corpus_files(w.entity, "corp", "npcs")
    assert out["error"] == "invalid" and "defines no kinds" in out["detail"]
    row = corpus_row(w)
    assert row.state is State.CORPUS_INVALID and "defines no kinds" in row.note
