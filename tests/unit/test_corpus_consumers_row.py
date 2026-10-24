"""T049: the fleet-level `consumers` row and the per-campaign reads diff (FR-024)."""

from __future__ import annotations

import re

import pytest

from mneme.corpus import consumers
from mneme.mempalace import conform
from mneme.mempalace.models import FAIL_STATES, ConformanceReport, State
from tests.fixtures.corpus_campaign import corpus_world

YAML = """\
schema: 1
consumers:
{entries}
"""


def _write(tmp_path, monkeypatch, entries: str):
    p = tmp_path / "consumers.yaml"
    p.write_text(YAML.format(entries=entries))
    monkeypatch.setattr(consumers, "DEFAULT", p)


IND = """\
  - name: cg.prep
    repo: CG
    entry: prep.py:1
    kinds: [grounding]
    mode: independent
{reads}"""


def _fleet(rep):
    rows = [r for r in rep.rows if r.dimension == "consumers" and r.campaign == conform.FLEET]
    assert len(rows) == 1
    return rows[0]


def test_real_inventory_row_appears_once_and_exits_zero(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    rep = conform.report(w.entity, runner=w.runner)
    row = _fleet(rep)
    assert row.state is State.CONSUMERS_OWED and row.state not in FAIL_STATES
    assert "non-compliant consumers" in row.note and "corpus consumers --noncompliant" in row.note
    assert conform.format_row(row).startswith("todo")
    only = ConformanceReport((row,))
    assert only.exit_code() == 0 and only.exit_code(strict=True) == 0


def test_invalid_file_fails(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    _write(tmp_path, monkeypatch, "  - name: x\n")
    row = _fleet(conform.report(w.entity, runner=w.runner))
    assert row.state is State.INVALID_CONFIG and "invalid" in row.note and "required" in row.note
    assert ConformanceReport((row,)).exit_code() == 1


def test_all_compliant_is_ok(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    _write(tmp_path, monkeypatch,
           "  - {name: a, repo: r, entry: e, kinds: [npcs], mode: palace}\n"
           "  - {name: b, repo: r, entry: e, kinds: [npcs], mode: toc}")
    rep = conform.report(w.entity, runner=w.runner)
    row = _fleet(rep)
    assert row.state is State.CONFORMANT and row.ok
    assert not [r for r in rep.rows if r.dimension == "consumers" and r.campaign != conform.FLEET]


def test_per_campaign_diff_both_directions_and_globs(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    # grounding = 4 files; party.md is also corpus. The consumer reads docs/*_state.md (misses
    # party.md and planning.md of its kind), docs/reviews/** (a decoy outside the corpus) and
    # docs/npcs/** (inside the corpus, so not an outside read).
    reads = ("    reads: ['docs/*_state.md', 'docs/reviews/**', 'docs/npcs/**', 'docs/*/z.md']\n")
    _write(tmp_path, monkeypatch, IND.format(reads=reads)
           + "  - {name: noreads, repo: r, entry: e, kinds: [npcs], mode: independent}")
    rep = conform.report(w.entity, "corp", runner=w.runner)
    assert _fleet(rep).state is State.CONSUMERS_OWED
    rows = [r for r in rep.rows if r.dimension == "consumers" and r.campaign == "corp"]
    assert len(rows) == 1 and rows[0].state is State.CONSUMERS_OWED
    note = rows[0].note
    assert "cg.prep reads outside the corpus: docs/reviews/x.md" in note  # ** spans dirs
    assert "campaign_state_draft" not in note  # `*` does not match the draft: *_state.md only
    outside = note.split("reads outside the corpus: ")[1].split(" |")[0]
    assert "docs/npcs" not in outside and "docs/campaign_state.md" not in outside
    missed = note.split("corpus files it does not read: ")[1]
    assert "docs/party.md" in missed and "docs/planning.md" in missed
    assert "docs/world_state.md" not in missed and "docs/campaign_state.md" not in missed
    assert "noreads" not in note  # named in the fleet count, not diffed
    assert ConformanceReport(tuple(rows)).exit_code(strict=True) == 0


def test_glob_semantics():
    g = conform._glob_match
    assert g("docs/a.md", "docs/*.md") and not g("docs/x/a.md", "docs/*.md")
    assert g("docs/x/y/a.md", "docs/**") and g("docs/x/y/a.md", "docs/**/*.md")
    assert g("docs/a.md", "docs/**/*.md") and not g("notes/a.md", "docs/**")


def test_wing_model_campaign_is_skipped_for_the_diff(tmp_path, monkeypatch):
    from tests.fixtures import entity_for, make_campaigns

    root = make_campaigns(tmp_path / "campaigns")
    ent = entity_for(root, mempalace=tmp_path / "mp")
    _write(tmp_path, monkeypatch, IND.format(reads="    reads: ['docs/**']\n"))
    rep = conform.report(ent, campaign="full")
    assert not [r for r in rep.rows if r.dimension == "consumers" and r.campaign == "full"]
    assert _fleet(rep).state is State.CONSUMERS_OWED


@pytest.mark.parametrize("pat,hit", [("a/**/c.md", "a/c.md"), ("a/**/c.md", "a/b/b/c.md")])
def test_double_star_middle(pat, hit):
    assert conform._glob_match(hit, pat)


GLOBS = [  # (pattern, path, expected) — explicit, so the test never depends on the Python version
    ("[Gg]*.vtt", "Gx.vtt", True), ("[Gg]*.vtt", "gx.vtt", True), ("[Gg]*.vtt", "x.vtt", False),
    ("[Gg]*.vtt", "d/Gx.vtt", False),
    ("summaries/*/x.md", "summaries/001/x.md", True),
    ("summaries/*/x.md", "summaries/x.md", False),
    ("summaries/*/x.md", "summaries/a/b/x.md", False),
    ("docs/**", "docs/a.md", True), ("docs/**", "docs/a/b/c.md", True), ("docs/**", "docs", False),
    ("docs/**", "notes/a.md", False),
    ("docs/**/*.md", "docs/a.md", True), ("docs/**/*.md", "docs/x/y/a.md", True),
    ("docs/**/*.md", "docs/a.txt", False),
    ("**/*.md", "a.md", True), ("**/*.md", "x/y/a.md", True), ("**/*.md", "a.txt", False),
    ("notes/**", "notes/t/x.md", True), ("notes/**", "notes", False),
    ("a/**/b", "a/b", True), ("a/**/b", "a/x/y/b", True), ("a/**/b", "a", False),
]


@pytest.mark.parametrize("pat,path,want", GLOBS)
def test_glob_table(pat, path, want):
    assert conform._glob_match(path, pat) is want
    from pathlib import PurePosixPath

    if hasattr(PurePosixPath, "full_match"):  # where the stdlib has it, we must agree
        assert PurePosixPath(path).full_match(pat) is want


def test_every_real_consumers_pattern_loads_and_matches_a_sample():

    for c in consumers.load(consumers.DEFAULT):
        for pat in c.reads:
            sample = pat.replace("**", "x/y").replace("*", "a").replace("?", "a")
            sample = re.sub(r"\[([^\]!])[^\]]*\]", r"\1", sample)
            assert conform._glob_match(sample, pat), (c.name, pat, sample)
