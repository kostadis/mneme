"""Feature 009 US1: `api.brief()` — the brief answer and its refusals (T007)."""

from __future__ import annotations

import hashlib
import json
import os

import pytest

from mneme.corpus import api
from mneme.mempalace import recipe as recipe_mod
from mneme.mempalace import runner as runner_mod
from tests.fixtures.corpus_campaign import corpus_world, write

KEYS = {"standard", "trust", "files", "bytes", "searchable", "searchable_files"}


@pytest.fixture
def w(tmp_path, monkeypatch):
    return corpus_world(tmp_path, monkeypatch)


def set_corpus(w, extra="", base=None):
    p = w.camp / ".mneme" / "corpus.yaml"
    p.write_text((base if base is not None else p.read_text()) + extra)
    return p


def ask(w):
    return api.brief(w.camp, recipe_mod.current())


def test_declared_order_is_kept(w):
    set_corpus(w, "brief:\n  - docs/planning.md\n  - docs/world_state.md\n")
    b = ask(w)["brief"]
    assert [e["path"] for e in b["brief"]] == ["docs/planning.md", "docs/world_state.md"]
    assert b["schema"] == 1 and b["campaign"] == "corp"
    assert list(b["kinds"]) == ["npcs", "summaries", "grounding", "party"]
    assert all(set(k) == KEYS for k in b["kinds"].values())


def test_shared_file_lists_both_kinds_and_one_trust(w):
    set_corpus(w, "brief:\n  - docs/party.md\n")
    (e,) = ask(w)["brief"]["brief"]
    assert e["kinds"] == ["grounding", "party"]
    assert isinstance(e["trust"], str)


def test_bytes_follow_os_stat_and_symlinks(w):
    write(w.camp, "docs/real.md", "x" * 123)
    os.symlink("real.md", w.camp / "docs" / "linked.md")
    set_corpus(w, "brief:\n  - docs/linked.md\n  - docs/planning.md\n",
               base=(w.camp / ".mneme/corpus.yaml").read_text().replace(
                   "dirs: [docs/npcs]", "dirs: [docs/npcs]\n    files: [docs/linked.md]"))
    b = ask(w)["brief"]
    e = b["brief"][0]
    assert e["path"] == "docs/linked.md" and e["bytes"] == os.stat(w.camp / "docs/linked.md").st_size == 123
    assert b["brief_bytes"] == sum(x["bytes"] for x in b["brief"])
    assert b["brief"][1]["bytes"] == os.stat(w.camp / "docs/planning.md").st_size


def test_searchable_files_excludes_unminable(w):
    write(w.camp, "docs/npcs/scan.pdf", "%PDF")
    set_corpus(w, "brief:\n  - docs/planning.md\n")
    npcs = ask(w)["brief"]["kinds"]["npcs"]
    assert npcs["files"] == 2 and npcs["searchable_files"] == 1 and npcs["searchable"] is True
    assert npcs["bytes"] == sum(os.stat(w.camp / f"docs/npcs/{n}").st_size
                                for n in ("a.md", "scan.pdf"))


def test_sha_and_no_contents_and_no_palace(w, monkeypatch):
    secret = "UNIQUE-SECRET-BODY-TEXT"
    write(w.camp, "docs/planning.md", secret)
    p = set_corpus(w, "brief:\n  - docs/planning.md\n")

    def boom(*a, **k):
        raise AssertionError("palace touched")
    monkeypatch.setattr(runner_mod.MempalaceRunner, "__init__", boom)
    monkeypatch.setattr(runner_mod.MempalaceRunner, "for_entity", boom)
    answer = ask(w)
    b = answer["brief"]
    assert b["corpus_sha256"] == hashlib.sha256(p.read_bytes()).hexdigest()
    assert secret not in json.dumps(answer)
    assert not any(v == secret for v in json.dumps(answer).split('"'))


def test_no_brief(w):
    a = ask(w)
    assert a["error"] == api.NO_BRIEF == "no-brief"
    assert "mneme corpus migrate-brief" in a["detail"]


def test_brief_unavailable_names_the_file(w):
    set_corpus(w, "brief:\n  - docs/planning.md\n  - docs/party.md\n")
    (w.camp / "docs" / "planning.md").unlink()
    a = ask(w)
    assert a["error"] == api.BRIEF_UNAVAILABLE and "docs/planning.md" in a["detail"]
    assert "docs/party.md" not in a["detail"]


def test_invalid(w):
    set_corpus(w, "bogus_key: 1\n")
    a = ask(w)
    assert a["error"] == "invalid" and a["findings"]


def test_not_declared(w):
    (w.camp / ".mneme" / "corpus.yaml").unlink()
    a = ask(w)
    assert a["error"] == "not-declared" and a["findings"] == []
