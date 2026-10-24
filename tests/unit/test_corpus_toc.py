"""The corpus TOC snapshot (feature 007, T015)."""

from __future__ import annotations

import json
import os
import subprocess

import pytest

from mneme.corpus import config, resolve, toc
from mneme.mempalace import recipe

REC = recipe.current()

BODY = (
    "campaign: c\nkinds:\n  npcs:\n    dirs: [docs/npcs]\n  summaries:\n    dirs: [docs/sums]\n"
    "  grounding:\n    files: [docs/party.md]\n"
)


@pytest.fixture
def camp(tmp_path):
    c = tmp_path / "camp"
    for rel, text in {
        "docs/npcs/a.md": "a", "docs/npcs/b.md": "b", "gen/g1/party.md": "party",
    }.items():
        (c / rel).parent.mkdir(parents=True, exist_ok=True)
        (c / rel).write_text(text)
    (c / "docs/sums").mkdir()  # declared but empty
    os.symlink("../gen/g1/party.md", c / "docs/party.md")
    (c / ".mneme").mkdir()
    (c / ".mneme/corpus.yaml").write_text(BODY)
    return c


def fresh(c):
    cfg = config.load(c, REC)
    return toc.build(resolve.resolve(cfg, c, REC), cfg, REC)


def test_build_matches_contract_shape(camp):
    doc = fresh(camp)
    assert doc["schema"] == 1 and doc["valid"] is True and doc["findings"] == []
    assert doc["campaign"] == "c" and doc["recipe_version"] == "3.0.0"
    assert len(doc["corpus_sha256"]) == 64 and doc["generated_by"].startswith("mneme ")
    g = doc["kinds"]["grounding"]
    assert g["standard"] is True and g["trust"] == "authoritative"
    assert g["files"][0]["path"] == "docs/party.md"
    assert g["files"][0]["target"] == "gen/g1/party.md"  # symlink carries target
    assert g["files"][0]["mined_as"] == "grounding" and g["files"][0]["minable"] is True
    assert "target" not in doc["kinds"]["npcs"]["files"][0]
    assert [f["path"] for f in doc["kinds"]["npcs"]["files"]] == [
        "docs/npcs/a.md", "docs/npcs/b.md"]
    assert g["not_materialized"] == [] and g["missing"] == []


def test_files_for_distinguishes_undeclared_from_empty(camp):
    doc = fresh(camp)
    assert toc.files_for(doc, "summaries") == []  # declared, empty
    assert toc.files_for(doc, "prep") is None  # not declared
    assert [f["path"] for f in toc.files_for(doc, "npcs")] == ["docs/npcs/a.md", "docs/npcs/b.md"]


def test_write_is_atomic_and_gitignores_itself(camp):
    path = toc.write(camp, fresh(camp))
    assert path == camp / ".mneme/corpus.toc.json"
    assert json.loads(path.read_text())["schema"] == 1
    assert [p.name for p in (camp / ".mneme").iterdir() if p.suffix == ".tmp"] == []
    assert (camp / ".gitignore").read_text() == ".mneme/corpus.toc.json\n"
    toc.write(camp, fresh(camp))  # second write: no duplicate line
    assert (camp / ".gitignore").read_text().count("corpus.toc.json") == 1


def test_gitignore_appended_to_existing_file_without_trailing_newline(camp):
    (camp / ".gitignore").write_text("*.log")
    toc.write(camp, fresh(camp))
    assert (camp / ".gitignore").read_text() == "*.log\n.mneme/corpus.toc.json\n"


def test_toc_is_actually_ignored_by_git(camp):
    subprocess.run(["git", "init", "-q"], cwd=camp, check=True)
    toc.write(camp, fresh(camp))
    r = subprocess.run(["git", "check-ignore", "-q", ".mneme/corpus.toc.json"], cwd=camp)
    assert r.returncode == 0


def test_read_missing_and_roundtrip(camp):
    assert toc.read(camp) is None
    doc = fresh(camp)
    toc.write(camp, doc)
    assert toc.read(camp) == doc


def test_verify_missing_then_ok(camp):
    assert toc.verify(camp, fresh(camp)).state == toc.MISSING
    toc.write(camp, fresh(camp))
    check = toc.verify(camp, fresh(camp))
    assert check.state == toc.OK and check.ok and check.reasons == ()


def test_file_added_to_declared_dir_after_render_is_stale(camp):
    toc.write(camp, fresh(camp))
    (camp / "docs/npcs/new.md").write_text("n")
    check = toc.verify(camp, fresh(camp))
    assert check.state == toc.STALE
    assert any("new.md" in r for r in check.reasons)


def test_hand_edited_files_with_stamp_kept_is_stale(camp):
    toc.write(camp, fresh(camp))
    path = camp / ".mneme/corpus.toc.json"
    doc = json.loads(path.read_text())
    doc["kinds"]["npcs"]["files"].pop()  # stamp untouched
    path.write_text(json.dumps(doc))
    check = toc.verify(camp, fresh(camp))
    assert check.state == toc.STALE and any("file set" in r for r in check.reasons)


def test_changed_content_and_repointed_symlink_are_stale(camp):
    toc.write(camp, fresh(camp))
    (camp / "docs/npcs/a.md").write_text("changed")
    assert toc.verify(camp, fresh(camp)).state == toc.STALE
    toc.write(camp, fresh(camp))
    (camp / "gen/g2").mkdir()
    (camp / "gen/g2/party.md").write_text("party")  # same bytes, new target
    os.remove(camp / "docs/party.md")
    os.symlink("../gen/g2/party.md", camp / "docs/party.md")
    assert toc.verify(camp, fresh(camp)).state == toc.STALE


def test_stamp_change_is_stale(camp):
    toc.write(camp, fresh(camp))
    (camp / ".mneme/corpus.yaml").write_text(BODY + "# note\n")
    check = toc.verify(camp, fresh(camp))
    assert check.state == toc.STALE and any("corpus_sha256" in r for r in check.reasons)


def test_unreadable_snapshot_is_stale_never_ok(camp):
    (camp / ".mneme/corpus.toc.json").write_text("{not json")
    assert toc.verify(camp, fresh(camp)).state == toc.STALE
    with pytest.raises(toc.TocError):
        toc.read(camp)
