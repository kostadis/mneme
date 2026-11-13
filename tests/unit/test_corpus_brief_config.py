"""`brief:` in corpus.yaml: structural findings and membership (feature 009, T003/T004/T006)."""

from __future__ import annotations

import subprocess

import pytest

from mneme.corpus import config, resolve
from mneme.mempalace import recipe

REC = recipe.current()

BASE = """\
campaign: corp
kinds:
  npcs:
    dirs: [docs/npcs]
  grounding:
    files:
      - docs/world_state.md
      - docs/planning.md
"""


def write(root, rel, text="x\n"):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


@pytest.fixture
def camp(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    for rel in ("docs/npcs/a.md", "docs/world_state.md", "docs/planning.md", "docs/other.md"):
        write(tmp_path, rel)
    (tmp_path / ".mneme").mkdir()
    return tmp_path


def parse(camp, brief):
    return config.parse((BASE + brief).encode(), REC, camp)


def struct(camp, brief):
    with pytest.raises(config.CorpusConfigError) as e:
        parse(camp, brief)
    return [(f.code, f.path) for f in e.value.findings]


def resolved(camp, brief):
    return resolve.resolve(parse(camp, brief), camp, REC)


def brief_findings(res):
    return [f.path for f in res.findings if f.code == "brief-undeclared"]


def test_valid_brief_parses_in_order(camp):
    cfg = parse(camp, "brief: [docs/planning.md, docs/world_state.md]\n")
    assert cfg.brief == ("docs/planning.md", "docs/world_state.md")
    assert brief_findings(resolved(camp, "brief: [docs/planning.md]\n")) == []


def test_no_brief_is_empty(camp):
    assert parse(camp, "").brief == ()


def test_duplicate_is_malformed(camp):
    assert struct(camp, "brief: [docs/planning.md, docs/planning.md]\n") == [
        ("malformed", "docs/planning.md")]


def test_empty_list(camp):
    assert [c for c, _ in struct(camp, "brief: []\n")] == ["empty-declaration"]


def test_escape(camp):
    assert struct(camp, "brief: ['../x.md']\n") == [("path-escape", "../x.md")]


@pytest.mark.parametrize("bad", ["brief: docs/planning.md\n", "brief: [1, 2]\n"])
def test_non_list_is_malformed(camp, bad):
    assert [c for c, _ in struct(camp, bad)] == ["malformed"]


def test_findings_reported_together(camp):
    got = struct(camp, "brief: [docs/planning.md, docs/planning.md, '../x.md']\n"
                       "bogus: 1\n")
    assert sorted(c for c, _ in got) == ["malformed", "path-escape", "unknown-key"]


def test_folder_is_undeclared(camp):
    assert brief_findings(resolved(camp, "brief: [docs/npcs]\n")) == ["docs/npcs"]


def test_file_outside_every_kind_is_undeclared(camp):
    assert brief_findings(resolved(camp, "brief: [docs/other.md]\n")) == ["docs/other.md"]


def test_gitignored_file_in_declared_dir_is_undeclared(camp):
    write(camp, "docs/npcs/secret.md")
    (camp / ".gitignore").write_text("docs/npcs/secret.md\n")
    res = resolved(camp, "brief: [docs/npcs/secret.md, docs/npcs/a.md]\n")
    assert brief_findings(res) == ["docs/npcs/secret.md"]


def test_declared_but_missing_is_not_a_finding(camp):
    (camp / "docs" / "planning.md").unlink()
    res = resolved(camp, "brief: [docs/planning.md]\n")
    assert brief_findings(res) == []


def test_skeleton_documents_brief_but_declares_none(camp):
    from mneme.corpus.cli import _skeleton

    text = _skeleton("corp")
    assert "# brief:" in text and "#   - docs/planning.md" in text
    assert not any(ln.startswith("brief:") for ln in text.splitlines())
    declared = text + "kinds:\n  npcs:\n    dirs: [docs/npcs]\n"
    cfg = config.parse(declared.encode(), REC, camp)
    assert cfg.brief == ()


def test_deleted_file_under_declared_dir_is_absent_not_a_finding(camp):
    (camp / "docs/npcs/a.md").unlink()
    cfg = parse(camp, "brief: [docs/npcs/a.md]\n")
    res = resolve.resolve(cfg, camp, REC)
    assert brief_findings(res) == []
    assert resolve.brief_standing(cfg, res, camp, "docs/npcs/a.md") == ("absent", ("npcs",))


def test_missing_declared_dir_as_brief_entry_is_undeclared(camp):
    import shutil
    shutil.rmtree(camp / "docs/npcs")
    res = resolved(camp, "brief: [docs/npcs]\n")
    assert brief_findings(res) == ["docs/npcs"]


def test_existing_ignored_file_under_dir_is_undeclared_standing(camp):
    write(camp, "docs/npcs/secret.md")
    (camp / ".gitignore").write_text("docs/npcs/secret.md\n")
    cfg = parse(camp, "brief: [docs/npcs/secret.md]\n")
    res = resolve.resolve(cfg, camp, REC)
    assert resolve.brief_standing(cfg, res, camp, "docs/npcs/secret.md")[0] == "undeclared"
