"""`brief_migrate`: a validated, append-only `brief:` edit of corpus.yaml (feature 009, T017)."""

from __future__ import annotations

import os
import subprocess

import pytest

from mneme.corpus import brief_migrate as bm
from mneme.corpus import config
from mneme.mempalace import recipe

REC = recipe.current()

# comments, blank lines, NO trailing newline
BASE = """\
# my corpus
campaign: corp

kinds:
  npcs:
    dirs: [docs/npcs]   # the cast
  grounding:
    files:
      - docs/world_state.md
      - docs/planning.md
"""
RAW = BASE.rstrip("\n").encode()


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
    (tmp_path / ".mneme/corpus.yaml").write_bytes(RAW)
    return tmp_path


def cy(camp):
    return camp / ".mneme" / "corpus.yaml"


def set_corpus(camp, data: bytes):
    cy(camp).write_bytes(data)


def refused(camp, code, files=bm.DEFAULT_FILES):
    before = cy(camp).read_bytes() if cy(camp).exists() else None
    r = bm.plan(camp, REC, files)
    assert isinstance(r, bm.Refusal) and r.code == code, r
    after = cy(camp).read_bytes() if cy(camp).exists() else None
    assert before == after
    return r


def test_preview_does_not_write(camp):
    p = bm.plan(camp, REC)
    assert isinstance(p, bm.Plan)
    assert p.block == "brief:\n  - docs/planning.md\n"
    assert p.files == (bm.BriefFile("docs/planning.md", ("grounding",), 2),)
    assert p.total_bytes == 2
    assert cy(camp).read_bytes() == RAW


def test_apply_without_trailing_newline(camp):
    p = bm.plan(camp, REC)
    out = bm.apply(p)
    assert out == cy(camp)
    new = cy(camp).read_bytes()
    assert new == RAW + b"\n\nbrief:\n  - docs/planning.md\n"
    assert new.startswith(RAW)
    assert config.parse(new, REC, camp).brief == ("docs/planning.md",)


def test_apply_with_trailing_newline(camp):
    orig = RAW + b"\n"
    set_corpus(camp, orig)
    bm.apply(bm.plan(camp, REC))
    new = cy(camp).read_bytes()
    assert new == orig + b"\nbrief:\n  - docs/planning.md\n"
    assert b"\n\n\n" not in new[len(orig) - 1:]
    assert config.parse(new, REC, camp).brief == ("docs/planning.md",)


def test_files_order_kept(camp):
    files = ("docs/world_state.md", "docs/planning.md")
    p = bm.plan(camp, REC, files)
    assert [f.path for f in p.files] == list(files)
    bm.apply(p)
    assert config.parse(cy(camp).read_bytes(), REC, camp).brief == files


def test_not_declared(tmp_path):
    refused(tmp_path, "not-declared")


def test_invalid_corpus(camp):
    set_corpus(camp, b"campaign: corp\nkinds:\n  npcs:\n    dirs: [../x]\n")
    r = refused(camp, "invalid")
    assert r.findings


@pytest.mark.parametrize("tail", ["brief: [docs/planning.md]\n", "brief:\n"])
def test_brief_exists(camp, tail):
    set_corpus(camp, RAW + b"\n" + tail.encode())
    refused(camp, "brief-exists")


def test_commented_brief_is_not_a_key(camp):
    set_corpus(camp, RAW + b"\n# brief:\n")
    p = bm.plan(camp, REC)
    assert isinstance(p, bm.Plan)
    bm.apply(p)
    assert config.parse(cy(camp).read_bytes(), REC, camp).brief == ("docs/planning.md",)


def test_undeclared(camp):
    r = refused(camp, "brief-undeclared", ("docs/nope.md",))
    assert "docs/nope.md" in r.detail
    refused(camp, "brief-undeclared", ("docs/other.md",))


def test_unavailable(camp):
    os.remove(camp / "docs/world_state.md")
    r = refused(camp, "brief-unavailable", ("docs/world_state.md",))
    assert "docs/world_state.md" in r.detail


def test_duplicate_is_invalid(camp):
    refused(camp, "invalid", ("docs/planning.md", "docs/planning.md"))


def test_escape_is_invalid(camp):
    refused(camp, "invalid", ("../x.md",))


def test_conflict_when_changed_since_plan(camp):
    p = bm.plan(camp, REC)
    changed = RAW + b"\n# edited\n"
    set_corpus(camp, changed)
    with pytest.raises(bm.MigrationConflict):
        bm.apply(p)
    assert cy(camp).read_bytes() == changed


def test_apply_is_atomic(camp, monkeypatch):
    p = bm.plan(camp, REC)

    def boom(*a, **k):
        raise OSError("disk gone")

    monkeypatch.setattr(bm.os, "replace", boom)
    with pytest.raises(OSError):
        bm.apply(p)
    assert cy(camp).read_bytes() == RAW
    assert [f.name for f in (camp / ".mneme").iterdir()] == ["corpus.yaml"]


def test_apply_keeps_file_mode(tmp_path, monkeypatch):
    import stat as _stat
    from mneme.corpus import brief_migrate as bm
    path = tmp_path / ".mneme" / "corpus.yaml"
    path.parent.mkdir()
    path.write_bytes(b"x: 1\n")
    path.chmod(0o644)
    bm._write_atomic(path, b"x: 2\n")
    assert _stat.S_IMODE(path.stat().st_mode) == 0o644
    assert path.read_bytes() == b"x: 2\n"
