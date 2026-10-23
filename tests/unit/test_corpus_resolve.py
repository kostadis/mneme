"""Resolving a declared corpus against a real git repo (feature 007, T014)."""

from __future__ import annotations

import hashlib
import os
import subprocess

import pytest

from mneme.corpus import config, resolve
from mneme.mempalace import recipe

REC = recipe.current()


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def init_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q")
    git(path, "config", "user.email", "t@t")
    git(path, "config", "user.name", "t")


def write(root, rel, text="x\n"):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def declare(root, body):
    (root / ".mneme").mkdir(exist_ok=True)
    (root / ".mneme" / "corpus.yaml").write_text(body)
    return config.load(root, REC)


def run(root, body):
    return resolve.resolve(declare(root, body), root, REC)


def codes(res):
    return [f.code for f in res.findings]


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


@pytest.fixture
def camp(tmp_path):
    init_repo(tmp_path / "camp")
    return tmp_path / "camp"


def test_dirs_expand_recursively_and_classify_minable(camp):
    write(camp, "docs/npcs/a.md", "a")
    write(camp, "docs/npcs/sub/b.md", "b")
    write(camp, "docs/npcs/scan.pdf", "pdf")
    res = run(camp, "campaign: c\nkinds:\n  npcs:\n    dirs: [docs/npcs]\n")
    assert res.valid and res.git == resolve.GIT_WORK_TREE
    files = {f.path: f for f in res.kinds["npcs"].files}
    assert set(files) == {"docs/npcs/a.md", "docs/npcs/sub/b.md", "docs/npcs/scan.pdf"}
    assert files["docs/npcs/a.md"].minable and files["docs/npcs/a.md"].sha256 == sha("a")
    assert not files["docs/npcs/scan.pdf"].minable
    assert files["docs/npcs/a.md"].mined_as == "npcs"
    assert res.mine_targets("npcs") == ["docs/npcs/a.md", "docs/npcs/sub/b.md"]


def test_missing_declared_path(camp):
    write(camp, "docs/a.md")
    res = run(camp, "campaign: c\nkinds:\n  npcs:\n    files: [docs/a.md, docs/gone.md]\n")
    assert res.kinds["npcs"].missing == ("docs/gone.md",)
    assert [f.path for f in res.kinds["npcs"].files] == ["docs/a.md"]
    assert res.valid  # missing is a status state, not a config finding


def test_sparse_skip_worktree_is_not_materialized_not_missing(camp):
    write(camp, "docs/keep.md")
    write(camp, "docs/far/x.md")
    write(camp, "docs/far/y.md")
    git(camp, "add", "-A")
    git(camp, "commit", "-qm", "i")
    git(camp, "update-index", "--skip-worktree", "docs/far/x.md", "docs/far/y.md")
    (camp / "docs/far/x.md").unlink()
    (camp / "docs/far/y.md").unlink()
    res = run(
        camp,
        "campaign: c\nkinds:\n  npcs:\n    dirs: [docs/far]\n  prep:\n    files: [docs/keep.md]\n",
    )
    k = res.kinds["npcs"]
    assert k.not_materialized == ("docs/far/x.md", "docs/far/y.md")
    assert k.missing == ()
    assert res.kinds["prep"].files and res.valid


def test_empty_corpus_when_nothing_resolves(camp):
    res = run(camp, "campaign: c\nkinds:\n  npcs:\n    files: [nope.md]\n")
    assert codes(res) == ["empty-corpus"]


def test_all_not_materialized_is_not_empty_corpus(camp):
    write(camp, "docs/x.md")
    git(camp, "add", "-A")
    git(camp, "commit", "-qm", "i")
    git(camp, "update-index", "--skip-worktree", "docs/x.md")
    (camp / "docs/x.md").unlink()
    res = run(camp, "campaign: c\nkinds:\n  npcs:\n    files: [docs/x.md]\n")
    assert res.valid and res.kinds["npcs"].not_materialized == ("docs/x.md",)


def test_out_of_the_abyss_symlink_chain(camp):
    """docs/party.md -> grounding/current/party.md, grounding/current -> generations/g72"""
    write(camp, "grounding/generations/g72/party.md", "party g72")
    os.symlink("generations/g72", camp / "grounding" / "current")
    (camp / "docs").mkdir()
    os.symlink("../grounding/current/party.md", camp / "docs" / "party.md")
    res = run(camp, "campaign: c\nkinds:\n  grounding:\n    files: [docs/party.md]\n")
    assert res.valid, res.findings
    (f,) = res.kinds["grounding"].files
    assert f.path == "docs/party.md"
    assert f.target == "grounding/generations/g72/party.md"
    assert f.sha256 == sha("party g72") and f.minable
    assert res.mine_targets("grounding") == ["grounding/generations/g72/party.md"]


def test_symlinked_directory_is_followed(camp):
    write(camp, "real/a.md", "a")
    os.symlink("real", camp / "linked")
    res = run(camp, "campaign: c\nkinds:\n  npcs:\n    dirs: [linked]\n")
    (f,) = res.kinds["npcs"].files
    assert (f.path, f.target) == ("linked/a.md", "real/a.md")


def test_symlink_loop_terminates(camp):
    write(camp, "d/a.md", "a")
    os.symlink("..", camp / "d" / "up")  # d/up -> campaign root
    res = run(camp, "campaign: c\nkinds:\n  npcs:\n    dirs: [d]\n")
    assert res.valid  # d/up points at an ancestor: not descended, no hang
    assert any(f.path == "d/a.md" for f in res.kinds["npcs"].files)


def test_symlink_outside_campaign(camp, tmp_path):
    write(tmp_path, "elsewhere/secret.md", "s")
    (camp / "docs").mkdir()
    os.symlink(tmp_path / "elsewhere" / "secret.md", camp / "docs" / "p.md")
    os.symlink(tmp_path / "elsewhere", camp / "docs" / "dirlink")
    write(camp, "docs/ok.md")
    res = run(camp, "campaign: c\nkinds:\n  npcs:\n    dirs: [docs]\n")
    out = [f for f in res.findings if f.code == "symlink-outside"]
    assert {f.path for f in out} == {"docs/p.md", "docs/dirlink"}
    assert [f.path for f in res.kinds["npcs"].files] == ["docs/ok.md"]


def test_declared_file_symlink_to_dir_and_dangling(camp):
    (camp / "d").mkdir()
    write(camp, "real/a.md")
    os.symlink("../real", camp / "d" / "asdir.md")
    os.symlink("nowhere.md", camp / "d" / "dangling.md")
    res = run(
        camp,
        "campaign: c\nkinds:\n  npcs:\n    files: [d/asdir.md, d/dangling.md, real/a.md]\n",
    )
    got = {f.path: f.code for f in res.findings}
    assert got == {"d/asdir.md": "symlink-not-file", "d/dangling.md": "symlink-not-file"}


def test_gitignored_declared_path_and_target(camp):
    write(camp, ".gitignore", "*.secret.md\nignored_dir/\n")
    write(camp, "docs/x.secret.md")
    write(camp, "docs/ok.md")
    write(camp, "ignored_dir/t.md")
    (camp / "docs").mkdir(exist_ok=True)
    os.symlink("../ignored_dir/t.md", camp / "docs" / "viaignored.md")
    res = run(camp, "campaign: c\nkinds:\n  npcs:\n    dirs: [docs]\n")
    ign = {f.path for f in res.findings if f.code == "gitignored"}
    assert ign == {"docs/x.secret.md", "ignored_dir/t.md"}


def test_tracked_file_matching_ignore_still_counts(camp):
    write(camp, "docs/a.md")
    git(camp, "add", "-A")
    git(camp, "commit", "-qm", "i")
    write(camp, ".gitignore", "docs/\n")
    res = run(camp, "campaign: c\nkinds:\n  npcs:\n    files: [docs/a.md]\n")
    assert "gitignored" in codes(res)  # mempalace's matcher would skip it


def test_file_shared_across_kinds_single_mark(camp):
    write(camp, "docs/party.md")
    write(camp, "docs/party/pc.md")
    res = run(
        camp,
        "campaign: c\nkinds:\n  party:\n    dirs: [docs/party]\n    files: [docs/party.md]\n"
        "    mined_as: true\n  grounding:\n    files: [docs/party.md]\n",
    )
    assert res.valid
    for kind in ("party", "grounding"):  # listed under BOTH kinds
        assert any(f.path == "docs/party.md" and f.mined_as == "party"
                   for f in res.kinds[kind].files)
    assert res.mine_targets("party") == ["docs/party.md", "docs/party/pc.md"]
    assert res.mine_targets("grounding") == []


def test_overlap_found_only_through_dirs(camp):
    write(camp, "docs/a.md")
    res = run(
        camp,
        "campaign: c\nkinds:\n  npcs:\n    dirs: [docs]\n  summaries:\n    dirs: [docs]\n",
    )
    assert codes(res) == ["ambiguous-mining-kind"]
    assert res.findings[0].path == "docs/a.md"


def test_dir_overlap_trust_conflict(camp):
    write(camp, "docs/a.md")
    res = run(
        camp,
        "campaign: c\nkinds:\n  npcs:\n    dirs: [docs]\n    mined_as: true\n"
        "  prep:\n    dirs: [docs]\n",
    )
    assert codes(res) == ["trust-conflict"]


def test_overlap_via_symlink_is_the_same_file(camp):
    write(camp, "gen/g1/party.md")
    (camp / "docs").mkdir()
    os.symlink("../gen/g1/party.md", camp / "docs" / "party.md")
    res = run(
        camp,
        "campaign: c\nkinds:\n  party:\n    files: [docs/party.md]\n"
        "  grounding:\n    dirs: [gen]\n",
    )
    assert codes(res) == ["ambiguous-mining-kind"]
    assert res.findings[0].path == "gen/g1/party.md"


def test_non_git_directory_is_reported_not_failed(tmp_path):
    c = tmp_path / "plain"
    write(c, "docs/a.md")
    write(c, ".gitignore", "docs/\n")  # inert outside a work tree
    res = run(c, "campaign: c\nkinds:\n  npcs:\n    dirs: [docs]\n")
    assert res.git == resolve.GIT_NOT_A_WORK_TREE
    assert res.valid and len(res.kinds["npcs"].files) == 1


def test_campaign_as_subdirectory_of_repo(tmp_path):
    init_repo(tmp_path / "repo")
    camp = tmp_path / "repo" / "sub" / "camp"
    write(camp, "docs/a.md")
    write(tmp_path / "repo", "other/zzz.md")
    git(tmp_path / "repo", "add", "-A")
    git(tmp_path / "repo", "commit", "-qm", "i")
    git(tmp_path / "repo", "update-index", "--skip-worktree", "sub/camp/docs/a.md")
    (camp / "docs/a.md").unlink()
    res = run(camp, "campaign: c\nkinds:\n  npcs:\n    files: [docs/a.md]\n")
    assert res.kinds["npcs"].not_materialized == ("docs/a.md",)


def test_inherited_git_dir_is_ignored(camp, monkeypatch, tmp_path):
    write(camp, "docs/a.md")
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "nowhere"))
    res = run(camp, "campaign: c\nkinds:\n  npcs:\n    dirs: [docs]\n")
    assert res.git == resolve.GIT_WORK_TREE
