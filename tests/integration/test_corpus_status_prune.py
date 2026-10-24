"""Quickstart scenarios 2 and 3 (US2): status proves the palace equals the corpus, and prune
removes exactly what was previewed (T032, T033)."""

from __future__ import annotations

import subprocess

import pytest

from mneme.mempalace import authority, backup, conform, prune, refresh, render
from mneme.mempalace import recipe as recipe_mod
from mneme.mempalace.models import FAIL_STATES, ConformanceReport, State
from mneme.mempalace.prune import PruneAbort
from tests.fixtures.corpus_campaign import DECLARED, DECOYS, corpus_world, write


def _cfg(w):
    return authority.load(w.camp, mempalace_root=w.store.parent.parent)


def settle(w):
    render.write_all(_cfg(w), recipe_mod.current(), w.camp)
    (res,) = refresh.refresh(w.entity, campaign="corp", runner=w.runner)
    assert not res.failed, res.error
    return res


def rows(w):
    rep = conform.report(w.entity, "corp", runner=w.runner)
    return {r.dimension: r for r in rep.rows}, rep


def corpus_row(w):
    return rows(w)[0]["corpus"]


def mine_decoy(w, rel="docs/campaign_state_draft.md", wing="root"):
    w.runner.mine_files(w.camp, [rel], wing=wing, palace=w.store)


def git(camp, *args):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=camp,
                   check=True, capture_output=True)


@pytest.fixture
def w(tmp_path, monkeypatch):
    world = corpus_world(tmp_path, monkeypatch)
    settle(world)
    return world


def test_a_settled_corpus_is_ok(w):
    r, rep = rows(w)
    assert r["corpus"].state is State.CONFORMANT, r["corpus"].note
    assert r["index"].state is State.BUILT
    assert "recipe" in r and r["recipe"].state is not State.DIVERGENT_UNDISPOSITIONED
    assert not any(x.state in FAIL_STATES for x in rep.rows if x.dimension == "corpus")


def test_undeclared_drawers(w):
    mine_decoy(w)
    row = corpus_row(w)
    assert row.state is State.UNDECLARED_DRAWERS and row.state in FAIL_STATES
    assert "docs/campaign_state_draft.md" in row.note and "mneme mp prune corp" in row.note
    assert rows(w)[0]["index"].state is State.STALE


def test_unmined_declared_file(w):
    write(w.camp, "docs/npcs/b.md")
    cfg = (w.camp / ".mneme" / "corpus.yaml").read_text()
    (w.camp / ".mneme" / "corpus.yaml").write_text(cfg)  # dirs: a new file under a declared dir
    row = corpus_row(w)
    assert row.state is State.UNMINED and "docs/npcs/b.md" in row.note
    assert "mneme mp refresh corp" in row.note


def test_stale_after_an_edit(w):
    write(w.camp, "docs/world_state.md", "# changed\n")
    row = corpus_row(w)
    assert row.state is State.CORPUS_STALE and "docs/world_state.md" in row.note


def test_missing_declared_path(w):
    p = w.camp / ".mneme" / "corpus.yaml"
    p.write_text(
        p.read_text().replace("files: [docs/party.md]", "files: [docs/party.md, docs/gone.md]")
    )
    row = corpus_row(w)
    assert row.state is State.CORPUS_MISSING and "docs/gone.md" in row.note


def test_unreadable_store_is_unknown_never_ok(w, monkeypatch):
    monkeypatch.setenv("MNEME_STUB_SOURCES", "rc1")
    row = corpus_row(w)
    assert row.state is State.CORPUS_UNKNOWN and not row.ok
    assert row.state not in FAIL_STATES
    _, rep = rows(w)  # the fixture has no faces, so judge only the corpus-derived rows
    mine = ConformanceReport(tuple(r for r in rep.rows if r.dimension in ("corpus", "index")))
    assert mine.exit_code() == 0 and mine.exit_code(strict=True) == 1


def test_edit_without_render_is_toc_stale(w):
    p = w.camp / ".mneme" / "corpus.yaml"
    p.write_text(p.read_text() + "# comment changes the stamp\n")
    row = corpus_row(w)
    assert row.state is State.TOC_STALE and "mneme mp render corp" in row.note


def test_a_content_edit_is_reported_once_as_toc_stale_not_stale_render(w):
    write(w.camp, "docs/npcs/b.md")  # the TOC snapshot is now out of date
    by, _ = rows(w)
    assert by["render"].state is State.CONFORMANT, by["render"].note
    assert by["corpus"].note.count("TOC-STALE") == 1


def test_wrong_wing_after_a_plain_mine(tmp_path, monkeypatch):
    w = corpus_world(tmp_path, monkeypatch)
    render.write_all(_cfg(w), recipe_mod.current(), w.camp)
    w.runner.mine_files(w.camp, ["docs/npcs/a.md"], wing="root", palace=w.store)
    row = corpus_row(w)
    assert "wrong-wing" in row.observed
    refresh.refresh(w.entity, campaign="corp", runner=w.runner)
    assert corpus_row(w).state is State.CONFORMANT  # refresh re-homes it


def test_combined_findings_are_all_listed(w):
    mine_decoy(w)
    write(w.camp, "docs/world_state.md", "# changed\n")
    row = corpus_row(w)
    assert "UNDECLARED-DRAWERS" in row.note and "STALE" in row.note


def test_exit_code_is_nonzero_for_a_real_finding(w):
    mine_decoy(w)
    _, rep = rows(w)
    assert rep.exit_code() == 1


# ── prune ────────────────────────────────────────────────────────────────────


def _prune(w, **kw):
    out: list[str] = []
    ok = prune.prune(w.entity, "corp", runner=w.runner, emit=out.append, **kw)
    return ok, out


def test_preview_then_confirm_removes_exactly_the_decoy(w):
    mine_decoy(w, wing="grounding")  # a wing the guard does not know: record is absent anyway
    before = w.source_rels()
    ok, out = _prune(w)
    assert ok and w.source_rels() == before  # a preview deletes nothing
    assert any("campaign_state_draft.md" in ln and "(1)" in ln for ln in out)
    assert any("--confirm --expect 1" in ln for ln in out)
    ok, out = _prune(w, confirm=True, expect=1, include_former_canon=("grounding",))
    assert ok, out
    assert w.source_rels() == set(DECLARED)
    assert corpus_row(w).state is State.CONFORMANT
    assert any(ln.startswith("backed up") for ln in out)
    assert any(ln.startswith("verified") for ln in out)


def test_expect_mismatch_aborts_before_anything(w):
    mine_decoy(w)
    before = w.sources()
    with pytest.raises(PruneAbort):
        _prune(w, confirm=True, expect=5, include_former_canon=("root",))
    assert w.sources() == before


def test_missing_file_drawers_are_pruned(w):
    (w.camp / "docs" / "npcs" / "a.md").unlink()
    ok, out = _prune(w, confirm=True, expect=1, include_former_canon=("npcs",))
    assert ok, out
    assert "docs/npcs/a.md" not in w.source_rels()


def test_skip_worktree_survivor(w):
    git(w.camp, "add", "-A")
    git(w.camp, "commit", "-qm", "i")
    git(w.camp, "update-index", "--skip-worktree", "docs/world_state.md")
    (w.camp / "docs" / "world_state.md").unlink()
    settle(w)  # re-render: the TOC now lists it as not_materialized
    r = corpus_row(w)
    assert r.state is State.CONFORMANT, r.note  # not-materialized is not a finding
    mine_decoy(w, wing="grounding")
    ok, out = _prune(w, confirm=True, expect=1, include_former_canon=("grounding",))
    assert ok, out
    assert "docs/world_state.md" in w.source_rels()  # its drawers survive
    assert any("not-materialized" in ln for ln in out)


def test_prune_never_touches_wing_model_path_for_corpus(w):
    _prune(w)
    assert not any(" sync " in f" {ln} " for ln in w.log_lines())


# ── regenerate (T032) ────────────────────────────────────────────────────────


def test_regenerate_with_decoys_leaves_exactly_the_toc(w, monkeypatch):
    mine_decoy(w)
    mine_decoy(w, "summaries/raw.md", wing="root")
    assert set(DECOYS) & w.source_rels()
    real_rmtree = backup.shutil.rmtree

    def clear(path, *a, **k):  # the stub keeps its drawers outside the store dir
        real_rmtree(path, *a, **k)
        w.state.unlink(missing_ok=True)

    monkeypatch.setattr(backup.shutil, "rmtree", clear)
    backup.regenerate(w.entity, "corp", runner=w.runner)
    assert w.source_rels() == set(DECLARED)
    assert corpus_row(w).state is State.CONFORMANT
    mines = [ln for ln in w.log_lines() if " mine " in f" {ln} " and "--help" not in ln]
    assert all("--files-from" in ln for ln in mines[-3:])


def test_regenerate_with_an_old_mempalace_deletes_nothing(w, monkeypatch):
    from mneme.mempalace.runner import MempalaceError

    (w.store / "keep").write_text("precious")
    monkeypatch.setenv("MNEME_STUB_OLD", "1")
    w.runner._read_gaps = w.runner._mine_gaps = None  # force a re-probe against the old CLI
    with pytest.raises(MempalaceError, match="nothing was deleted"):
        backup.regenerate(w.entity, "corp", runner=w.runner)
    assert (w.store / "keep").read_text() == "precious"


# ── round 4: capability split, probe failure, sidecar-only store ─────────────


def _fake_help(w, monkeypatch, *, mine=None, top=None):
    """Make the stub's `--help` probes answer as given: (rc, stdout) per probe, else real."""
    real = w.runner.runner
    w.runner._read_gaps = w.runner._mine_gaps = None

    def run(cmd):
        if "--help" in cmd:
            ans = mine if "mine" in cmd else top
            if ans is not None:
                return subprocess.CompletedProcess(cmd, ans[0], stdout=ans[1], stderr="boom")
        return real(cmd)

    monkeypatch.setattr(w.runner, "runner", run)


def test_status_and_prune_need_only_sources_and_forget(w, monkeypatch):
    # I1: a mempalace without `mine --skips-json` still reads and forgets.
    _fake_help(w, monkeypatch, mine=(0, "usage: mine DIR [--files-from F]"))
    assert corpus_row(w).state is State.CONFORMANT
    mine_decoy(w)
    ok, _ = _prune(w)
    assert ok
    assert w.runner.supports_corpus() is False
    assert "mine --skips-json" in w.runner.too_old_message()
    assert "sources" not in w.runner.too_old_message()


def test_unrunnable_probe_is_unknown_not_too_old(w, monkeypatch):
    # I2: `--help` crashing is not "too old", and the failure is not cached.
    _fake_help(w, monkeypatch, top=(1, ""), mine=(1, ""))
    row = corpus_row(w)
    assert row.state is State.CORPUS_UNKNOWN
    assert "cannot probe mempalace capabilities" in row.note and "too old" not in row.note
    assert "lacks corpus support" not in row.note
    monkeypatch.undo()
    w.runner._read_gaps = w.runner._mine_gaps = None
    assert w.runner.supports_corpus() is True


def test_sidecar_only_store_reads_as_not_provisioned(w, monkeypatch):
    # I3: a failed first bringup leaves only mneme-*.json in the store dir.
    import shutil

    shutil.rmtree(w.store)
    w.store.mkdir(parents=True)
    (w.store / "mneme-former-wings.json").write_text("{}")
    monkeypatch.setenv("MNEME_STUB_SOURCES", "rc1")  # a real mempalace cannot open no palace
    row = corpus_row(w)
    assert row.state is State.CORPUS_UNKNOWN
    assert "not provisioned" in row.note and "sources" not in row.note
    assert "embedder" not in rows(w)[0]
