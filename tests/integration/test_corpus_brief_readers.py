"""Feature 009 US1: CLI and MCP answer the brief identically (T008; SC-004/005/007)."""

from __future__ import annotations

import json
import shutil

import pytest
from typer.testing import CliRunner

from mneme.cli import app
from mneme.corpus import config as cconfig
from mneme.mcp import server
from mneme.mempalace import recipe as recipe_mod
from mneme.mempalace.cli import EXIT_RUNTIME
from mneme.mempalace.corpus_guard import migrate_shadowed
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


# ── T012: `corpus check` and the brief ──────────────────────────────────────────


def _planning_bytes(w):
    return (w.camp / "docs" / "planning.md").stat().st_size


def test_check_prints_brief_line_before_valid(w):
    r = CLI.invoke(app, ["corpus", "check", "corp"])
    assert r.exit_code == 0, r.output
    lines = r.stdout.splitlines()
    assert lines[-2] == f"brief: 1 file(s), {_planning_bytes(w)} bytes"
    assert lines[-1] == "corpus is valid"


def test_check_brief_not_declared(w):
    _strip_brief(w)
    r = CLI.invoke(app, ["corpus", "check", "corp"])
    assert r.exit_code == 0, r.output
    assert r.stdout.splitlines()[-2:] == ["brief: not declared", "corpus is valid"]


def test_check_notes_brief_file_not_on_this_checkout(w):
    p = w.camp / ".mneme" / "corpus.yaml"
    p.write_text(p.read_text().replace("brief:\n  - docs/planning.md\n",
                                       "brief:\n  - docs/planning.md\n  - docs/party.md\n"))
    (w.camp / "docs" / "party.md").unlink()
    r = CLI.invoke(app, ["corpus", "check", "corp"])
    assert r.exit_code == 0, r.output
    assert r.stdout.splitlines()[-2] == (
        f"brief: 2 file(s), {_planning_bytes(w)} bytes (1 not on this checkout)")


def _undeclared(w):
    write(w.camp, "docs/other.md")
    p = w.camp / ".mneme" / "corpus.yaml"
    p.write_text(p.read_text().replace("brief:\n  - docs/planning.md\n",
                                       "brief:\n  - docs/other.md\n"))


def test_check_and_toc_refuse_brief_undeclared(w):
    _undeclared(w)
    for cmd in ("check", "toc"):
        r = CLI.invoke(app, ["corpus", cmd, "corp"])
        assert r.exit_code != 0, (cmd, r.output)
        assert "brief-undeclared" in r.stderr and "docs/other.md" in r.stderr


# ── T015: every refusal, CLI and MCP ────────────────────────────────────────────


def _strip_brief(w):
    p = w.camp / ".mneme" / "corpus.yaml"
    p.write_text(p.read_text().replace("brief:\n  - docs/planning.md\n", ""))


def _cli_refusal(*extra):
    r = CLI.invoke(app, ["corpus", "brief", "corp", "--json", *extra])
    assert r.exit_code == EXIT_RUNTIME, r.output
    assert r.stderr.startswith("error: ") and len(r.stderr.strip()) > len("error:")
    assert r.stdout.strip() == ""  # no brief/kinds on stdout
    return r


def _mcp_refusal(w, code):
    out = server.corpus_brief(w.entity, "corp")
    assert out["error"] == code and out["detail"]
    assert "brief" not in out and "kinds" not in out
    return out


def test_refuse_not_declared(w):
    (w.camp / ".mneme" / "corpus.yaml").unlink()
    r = _cli_refusal()
    assert "no corpus" in r.stderr
    _mcp_refusal(w, "not-declared")


def test_refuse_invalid_names_check_finding(w):
    _undeclared(w)
    check = CLI.invoke(app, ["corpus", "check", "corp"])
    r = _cli_refusal()
    assert "brief-undeclared" in r.stderr and "brief-undeclared" in check.stderr
    out = _mcp_refusal(w, "invalid")
    assert "brief-undeclared" in out["detail"]


def test_refuse_no_brief_is_not_the_map_alone(w):
    _strip_brief(w)
    r = _cli_refusal()
    assert "migrate-brief" in r.stderr
    _mcp_refusal(w, "no-brief")


def test_refuse_brief_unavailable_names_file(w):
    (w.camp / "docs" / "planning.md").unlink()
    r = _cli_refusal()
    assert "docs/planning.md" in r.stderr
    out = _mcp_refusal(w, "brief-unavailable")
    assert "docs/planning.md" in out["detail"]


def test_refuse_second_checkout_store_alias_clash(w, tmp_path):
    other = tmp_path / "elsewhere" / "corp"
    shutil.copytree(w.camp, other)
    r = _cli_refusal("--dir", str(other))
    assert "store alias 'corp'" in r.stderr and "2 campaigns" in r.stderr
    # MCP `corpus_brief` takes no --dir, so it cannot be pointed at the second checkout: CLI only.


# ── T020: migrate-brief ─────────────────────────────────────────────────────────


def _corpus_bytes(camp):
    return (camp / ".mneme" / "corpus.yaml").read_bytes()


def test_migrate_preview_apply_then_brief_then_refuse(w):
    _strip_brief(w)
    before = _corpus_bytes(w.camp)
    r = CLI.invoke(app, ["corpus", "migrate-brief", "corp"])
    assert r.exit_code == 0, r.output
    lines = r.stdout.splitlines()
    assert lines[0] == "== corp"
    assert "    brief:" in lines and "      - docs/planning.md" in lines
    assert f"  docs/planning.md  [grounding] {_planning_bytes(w)}" in lines
    assert f"  total: {_planning_bytes(w)} bytes" in lines
    assert lines[-1] == "preview only; re-run with --apply to write"
    assert _corpus_bytes(w.camp) == before

    r = CLI.invoke(app, ["corpus", "migrate-brief", "corp", "--apply"])
    assert r.exit_code == 0, r.output
    assert r.stdout.splitlines()[-1].startswith("applied: ")
    after = _corpus_bytes(w.camp)
    assert after.startswith(before) and after.endswith(b"brief:\n  - docs/planning.md\n")

    assert "docs/planning.md" in [b["path"] for b in cli_json()["brief"]]

    r = CLI.invoke(app, ["corpus", "migrate-brief", "corp", "--apply"])
    assert r.exit_code == EXIT_RUNTIME
    assert "refused: brief-exists:" in r.stdout
    assert _corpus_bytes(w.camp) == after


def test_migrate_undeclared_file_refuses_writes_nothing(w):
    _strip_brief(w)
    before = _corpus_bytes(w.camp)
    r = CLI.invoke(app, ["corpus", "migrate-brief", "corp", "--file", "docs/nope.md", "--apply"])
    assert r.exit_code == EXIT_RUNTIME
    assert "refused: brief-undeclared:" in r.stdout
    assert _corpus_bytes(w.camp) == before


def test_migrate_needs_exactly_one_of_campaign_or_all(w):
    for args in ([], ["corp", "--all"]):
        r = CLI.invoke(app, ["corpus", "migrate-brief", *args])
        assert r.exit_code == 2, r.output


def test_migrate_all_applies_the_rest_and_exits_nonzero(w):
    # corp already has a brief; corp2 does not.
    two = w.root / "corp2"
    shutil.copytree(w.camp, two)
    for rel, old, new in ((".mneme/corpus.yaml", "campaign: corp", "campaign: corp2"),
                          (".mneme/mempalace.yaml", "corp", "corp2")):
        t = (two / rel).read_text().replace(old, new)
        (two / rel).write_text(t)
    q = two / ".mneme" / "corpus.yaml"
    q.write_text(q.read_text().replace("brief:\n  - docs/planning.md\n", ""))
    first = _corpus_bytes(w.camp)
    r = CLI.invoke(app, ["corpus", "migrate-brief", "--all", "--apply"])
    assert r.exit_code == EXIT_RUNTIME, r.output
    assert "== corp\nrefused: brief-exists:" in r.stdout
    assert "== corp2" in r.stdout and "applied: " in r.stdout
    assert _corpus_bytes(w.camp) == first
    assert _corpus_bytes(two).endswith(b"brief:\n  - docs/planning.md\n")


# ── T021: R12 — adopt keeps the brief block ─────────────────────────────────────


def test_migrate_shadowed_keeps_brief_block(w):
    auth = w.camp / ".mneme" / "mempalace.yaml"
    auth.write_text(auth.read_text().replace('"4.0.0"', '"3.0.0"'))
    for rel in ("docs/arcs/a.md",):
        write(w.camp, rel)
    cy = w.camp / ".mneme" / "corpus.yaml"
    cy.write_text(cy.read_text() + "campaign_kinds:\n  arcs:\n    dirs: [docs/arcs]\n"
                  "    trust: authoritative\n")
    before = cy.read_text()
    rec = recipe_mod.current()
    got = migrate_shadowed("adopt", "corp", w.camp, rec)
    assert got is not None, "the current recipe should make `arcs` a standard kind"
    new, moved = got
    assert moved == ["arcs"]
    assert "brief:\n  - docs/planning.md\n" in new
    assert new.count("brief:") == before.count("brief:") == 1
    cfg = cconfig.parse(new.encode(), rec, w.camp)
    assert cfg.brief == ("docs/planning.md",)


def test_migrate_all_skips_campaign_shared_dirs(w, monkeypatch):
    # gm-assistant / scripts sit beside campaigns in a clone; they are not campaigns (008).
    import dataclasses
    (w.root / "scripts").mkdir()
    ent = dataclasses.replace(w.entity, campaign_shared_dirs=("scripts",))
    monkeypatch.setattr("mneme.corpus.cli._load_or_exit", lambda _c: ent)
    r = CLI.invoke(app, ["corpus", "migrate-brief", "--all"])
    assert "== scripts" not in r.stdout
    assert "== corp" in r.stdout
