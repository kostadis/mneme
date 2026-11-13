"""Feature 009 US1: CLI and MCP answer the brief identically (T008; SC-004/005/007)."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from mneme.cli import app
from mneme.mcp import server
from tests.fixtures.corpus_campaign import corpus_world, write

CLI = CliRunner()


@pytest.fixture
def w(tmp_path, monkeypatch):
    world = corpus_world(tmp_path, monkeypatch)
    p = world.camp / ".mneme" / "corpus.yaml"
    p.write_text(p.read_text() + "brief:\n  - docs/planning.md\n")
    monkeypatch.setattr("mneme.mempalace.cli._load_or_exit", lambda _c: world.entity)
    monkeypatch.setattr("mneme.corpus.cli._load_or_exit", lambda _c: world.entity)
    return world


def cli_json():
    r = CLI.invoke(app, ["corpus", "brief", "corp", "--json"])
    assert r.exit_code == 0, r.output
    return json.loads(r.stdout)


def test_cli_and_mcp_agree(w):
    assert cli_json() == server.corpus_brief(w.entity, "corp")


def test_new_file_counts_with_no_render(w):
    before = cli_json()["kinds"]["npcs"]["files"]
    write(w.camp, "docs/npcs/b.md")
    assert cli_json()["kinds"]["npcs"]["files"] == before + 1
    assert server.corpus_brief(w.entity, "corp")["kinds"]["npcs"]["files"] == before + 1


def test_answer_is_small(w):
    assert len(json.dumps(cli_json())) < 2048


def test_human_form(w):
    r = CLI.invoke(app, ["corpus", "brief", "corp"])
    assert r.exit_code == 0, r.output
    lines = r.stdout.splitlines()
    assert lines[0].startswith("brief (1 file(s), ") and lines[0].endswith("bytes):")
    assert lines[1].startswith("  docs/planning.md  [grounding] ")
    assert lines[2] == "kinds:"
    kind_lines = lines[3:]
    assert len(kind_lines) == 4
    assert kind_lines[0].startswith("  npcs (") and "searchable" in kind_lines[0]


def test_refusals(w):
    p = w.camp / ".mneme" / "corpus.yaml"
    p.write_text(p.read_text().replace("brief:\n  - docs/planning.md\n", ""))
    r = CLI.invoke(app, ["corpus", "brief", "corp"])
    assert r.exit_code != 0 and "migrate-brief" in r.output
    out = server.corpus_brief(w.entity, "corp")
    assert out["error"] == "no-brief" and out["campaign"] == "corp"
