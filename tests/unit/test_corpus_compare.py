"""The corpus finding state matrix (feature 007, T027-T029, SC-004).

One case per finding, combinations, and unknown. Every non-matching case is not OK."""

from __future__ import annotations

import os

import pytest

from mneme.corpus import compare as C
from mneme.corpus import toc as T
from mneme.corpus.config import Finding
from mneme.corpus.resolve import ResolvedCorpus, ResolvedFile, ResolvedKind
from mneme.mempalace.corpus_record import CorpusRecord
from mneme.mempalace.runner import SourceRecord

OK_TOC = T.TocCheck(T.OK)
SHA = "a" * 64


def _f(path, kind="npcs", sha=SHA, minable=True, target=None):
    return ResolvedFile(path, sha, minable, kind, target)


def _resolved(tmp_path, files=(), *, missing=(), nm=(), findings=()):
    by: dict[str, list] = {}
    for f in files:
        by.setdefault(f.mined_as, []).append(f)
    kinds = {k: ResolvedKind(k, True, "authoritative", tuple(v)) for k, v in by.items()}
    kinds.setdefault("npcs", ResolvedKind("npcs", True, "authoritative"))
    k = kinds["npcs"]
    kinds["npcs"] = ResolvedKind(k.name, k.standard, k.trust, k.files, tuple(nm), tuple(missing))
    return ResolvedCorpus("corp", kinds, tuple(findings))


def _src(tmp_path, rel, wing="npcs", drawers=2):
    (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / rel).touch()
    return SourceRecord(wing, str((tmp_path / rel).resolve()), 1.0, drawers)


def _rec(*paths, sha=SHA, kind="npcs"):
    return CorpusRecord("t", "corp", "x", {p: {"kind": kind, "sha256": sha, "target": p}
                                           for p in paths})


def run(tmp_path, resolved, sources, record=None, toc=OK_TOC, **kw):
    return C.compare(resolved, sources, record, toc, tmp_path, **kw)


def test_exact_match_is_ok(tmp_path):
    r = _resolved(tmp_path, [_f("a.md")])
    res = run(tmp_path, r, [_src(tmp_path, "a.md")], _rec("a.md"))
    assert res.ok and res.codes == () and res.deletion == ()


def test_undeclared_drawers(tmp_path):
    r = _resolved(tmp_path, [_f("a.md")])
    res = run(tmp_path, r, [_src(tmp_path, "a.md"), _src(tmp_path, "decoy.md", drawers=3)],
              _rec("a.md"))
    assert res.codes == (C.UNDECLARED,)
    f = res.get(C.UNDECLARED)
    assert f.files == ("decoy.md",) and f.drawers == 3 and "prune" in f.remedy
    assert [s.drawers for s in res.deletion] == [3]


def test_unmined(tmp_path):
    r = _resolved(tmp_path, [_f("a.md"), _f("b.md")])
    res = run(tmp_path, r, [_src(tmp_path, "a.md")], _rec("a.md"))
    assert res.codes == (C.UNMINED,) and res.get(C.UNMINED).files == ("b.md",)


def test_non_minable_file_is_never_unmined(tmp_path):
    r = _resolved(tmp_path, [_f("a.md"), _f("pic.png", minable=False)])
    assert run(tmp_path, r, [_src(tmp_path, "a.md")], _rec("a.md")).ok


def test_stale_when_sha_differs(tmp_path):
    r = _resolved(tmp_path, [_f("a.md", sha="b" * 64)])
    res = run(tmp_path, r, [_src(tmp_path, "a.md")], _rec("a.md"))
    assert res.codes == (C.STALE,) and "refresh" in res.get(C.STALE).remedy


def test_stale_when_symlink_repointed(tmp_path):
    r = _resolved(tmp_path, [_f("cur/a.md", target="gen2/a.md")])
    rec = CorpusRecord("t", "corp", "x", {"cur/a.md": {"kind": "npcs", "sha256": SHA,
                                                       "target": "gen1/a.md"}})
    res = run(tmp_path, r, [_src(tmp_path, "gen2/a.md")], rec)
    assert res.codes == (C.STALE,)


def test_no_record_cannot_vouch_for_held_files(tmp_path):
    r = _resolved(tmp_path, [_f("a.md")])
    res = run(tmp_path, r, [_src(tmp_path, "a.md")], None)
    assert res.codes == (C.STALE,)


def test_missing_declared_path_and_its_drawers_are_pruned(tmp_path):
    r = _resolved(tmp_path, [_f("a.md")], missing=["gone.md"])
    res = run(tmp_path, r, [_src(tmp_path, "a.md"), _src(tmp_path, "gone.md")], _rec("a.md"))
    assert res.codes == (C.MISSING,)  # its drawers are reported under missing, not undeclared
    assert res.get(C.MISSING).files == ("gone.md",) and res.get(C.MISSING).drawers == 2
    assert [os.path.basename(s.source_file) for s in res.deletion] == ["gone.md"]


def test_missing_without_drawers_is_still_a_finding(tmp_path):
    r = _resolved(tmp_path, [_f("a.md")], missing=["gone.md"])
    res = run(tmp_path, r, [_src(tmp_path, "a.md")], _rec("a.md"))
    assert res.codes == (C.MISSING,) and res.deletion == ()


def test_not_materialized_is_never_a_finding_and_never_deleted(tmp_path):
    r = _resolved(tmp_path, [_f("a.md")], nm=["sparse/x.md"])
    (tmp_path / "sparse").mkdir()
    ghost = SourceRecord("npcs", str((tmp_path / "sparse" / "x.md").resolve()), 1.0, 4)
    res = run(tmp_path, r, [_src(tmp_path, "a.md"), ghost], _rec("a.md"))
    assert res.ok and res.deletion == () and res.spared == (ghost,)


def test_wrong_wing(tmp_path):
    r = _resolved(tmp_path, [_f("a.md")])
    res = run(tmp_path, r, [_src(tmp_path, "a.md", wing="root")], _rec("a.md"))
    assert res.codes == (C.WRONG_WING,) and "refresh" in res.get(C.WRONG_WING).remedy
    assert res.deletion == ()  # a declared file is never in the prune set


def test_right_wing_and_another_wing_reports_wrong_wing_only(tmp_path):
    r = _resolved(tmp_path, [_f("a.md")])
    srcs = [_src(tmp_path, "a.md"), _src(tmp_path, "a.md", wing="root")]
    res = run(tmp_path, r, srcs, _rec("a.md"))
    assert res.codes == (C.WRONG_WING,)


def test_out_of_scope(tmp_path):
    r = _resolved(tmp_path, [_f("a.md")])
    res = run(tmp_path, r, [_src(tmp_path, "a.md"), SourceRecord("npcs", "/elsewhere/z.md", 1, 1)],
              _rec("a.md"))
    assert res.codes == (C.OUT_OF_SCOPE,) and res.deletion == ()


def test_invalid_declaration_compares_nothing(tmp_path):
    r = _resolved(tmp_path, [_f("a.md")], findings=[Finding("gitignored", "x", path="a.md")])
    res = run(tmp_path, r, [_src(tmp_path, "decoy.md")], _rec("a.md"))
    assert res.codes == (C.INVALID,) and not res.verified and res.deletion == ()


@pytest.mark.parametrize("record_error", [None, "bad json"])
def test_unknown_when_sources_is_none(tmp_path, record_error):
    r = _resolved(tmp_path, [_f("a.md")])
    res = run(tmp_path, r, None, _rec("a.md"), record_error=record_error)
    assert res.codes == (C.UNKNOWN,) and not res.ok and not res.verified


def test_unknown_when_the_record_is_unreadable(tmp_path):
    r = _resolved(tmp_path, [_f("a.md")])
    res = run(tmp_path, r, [_src(tmp_path, "a.md")], None, record_error="bad json")
    assert res.codes == (C.UNKNOWN,)
    assert C.STALE not in res.codes  # staleness is unknown, not guessed


@pytest.mark.parametrize("state", [T.MISSING, T.STALE])
def test_toc_stale(tmp_path, state):
    r = _resolved(tmp_path, [_f("a.md")])
    res = run(tmp_path, r, [_src(tmp_path, "a.md")], _rec("a.md"),
              toc=T.TocCheck(state, ("file set differs",)))
    assert res.codes == (C.TOC_STALE,) and "render" in res.get(C.TOC_STALE).remedy


def test_findings_combine_and_keep_full_lists(tmp_path):
    files = [_f(f"n{i}.md") for i in range(12)]
    r = _resolved(tmp_path, files, missing=["gone.md"])
    srcs = [_src(tmp_path, "decoy.md")]
    res = run(tmp_path, r, srcs, None, toc=T.TocCheck(T.STALE, ("x",)))
    assert set(res.codes) == {C.UNDECLARED, C.UNMINED, C.MISSING, C.TOC_STALE}
    assert res.get(C.UNMINED).count == 12  # truncation is display-only
    assert not res.ok


def test_symlink_and_its_target_both_declared_are_both_held(tmp_path):
    """A symlink and its target declared together share one real file's drawers; neither
    declared path is unmined or stale (review A1)."""
    real = _src(tmp_path, "chapters/ch9.md", wing="summaries")
    (tmp_path / "current.md").symlink_to("chapters/ch9.md")
    r = ResolvedCorpus("corp", {"summaries": ResolvedKind("summaries", True, "authoritative", (
        _f("chapters/ch9.md", "summaries", target=None),
        _f("current.md", "summaries", target="chapters/ch9.md"),
    )), "npcs": ResolvedKind("npcs", True, "authoritative")})
    # the link's mined_path is its target
    rec = CorpusRecord("t", "corp", "x", {
        p: {"kind": "summaries", "sha256": SHA, "target": t}
        for p, t in (("chapters/ch9.md", "chapters/ch9.md"), ("current.md", "chapters/ch9.md"))
    })
    res = run(tmp_path, r, [real], rec)
    assert res.ok, [(f.code, f.files) for f in res.findings]


def test_classify_scales_with_thousands_of_not_materialized_entries(tmp_path):
    """Matching stays near-linear for a sparse directory link expanded per file (F3)."""
    import time
    n = 3000
    nm = [f"lore/d{i % 30}/f{i}.md" for i in range(n)]
    r = _resolved(tmp_path, [_f("a.md")], nm=nm)
    sources = [SourceRecord("npcs", str(tmp_path / nm[i]), 1.0, 1) for i in range(n)]
    sources += [_src(tmp_path, "a.md"), SourceRecord("npcs", str(tmp_path / "zz/u.md"), 1.0, 1)]
    t = time.perf_counter()
    c = C.classify(r, sources, tmp_path)
    assert time.perf_counter() - t < 1.0
    assert len(c.spared) == n
    assert [s.source_file for s in c.undeclared] == [str(tmp_path / "zz/u.md")]
