"""`mneme-corpus-mined.json` (007 T019)."""

from __future__ import annotations

import pytest

from mneme.mempalace import corpus_record as rec


def e(kind, sha="s", target="t"):
    return {"kind": kind, "sha256": sha, "target": target}


def test_missing_is_none_and_roundtrip(tmp_path):
    assert rec.read(tmp_path) is None
    rec.write(tmp_path, "c", "csha", {"a.md": e("npcs")})
    r = rec.read(tmp_path)
    assert r.campaign == "c" and r.corpus_sha256 == "csha" and r.files == {"a.md": e("npcs")}
    assert not list(tmp_path.glob(".*.tmp"))


def test_merge_replaces_only_its_own_kind(tmp_path):
    rec.merge_kind(tmp_path, "c", "x", "npcs", {"a.md": e("npcs"), "b.md": e("npcs")})
    rec.merge_kind(tmp_path, "c", "x", "party", {"p.md": e("party")})
    rec.merge_kind(tmp_path, "c", "x", "npcs", {"a.md": e("npcs", "new")})  # b.md left the kind
    assert set(rec.read(tmp_path).files) == {"a.md", "p.md"}
    assert rec.read(tmp_path).files["a.md"]["sha256"] == "new"


def test_unreadable_record_raises(tmp_path):
    (tmp_path / rec.FILENAME).write_text("{not json")
    with pytest.raises(rec.CorpusRecordError):
        rec.read(tmp_path)
    (tmp_path / rec.FILENAME).write_text('{"schema": 9, "files": {}, "mined_at": "x"}')
    with pytest.raises(rec.CorpusRecordError, match="schema"):
        rec.read(tmp_path)
    (tmp_path / rec.FILENAME).write_text(
        '{"schema": 1, "mined_at": "x", "files": {"a": {"kind": "k"}}}'
    )
    with pytest.raises(rec.CorpusRecordError):
        rec.read(tmp_path)


def test_merge_over_an_unreadable_record_starts_fresh(tmp_path):
    (tmp_path / rec.FILENAME).write_text("garbage")
    rec.merge_kind(tmp_path, "c", "x", "npcs", {"a.md": e("npcs")})
    assert set(rec.read(tmp_path).files) == {"a.md"}
