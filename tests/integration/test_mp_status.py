"""US2 integration test (T018): honest status over mixed fixtures via the stub binary."""

from __future__ import annotations

from mneme.mempalace import conform
from mneme.mempalace.models import State
from mneme.mempalace.runner import MempalaceRunner
from tests.fixtures import STUB, add_store_pointer, entity_for, make_campaigns


def _runner(monkeypatch, tmp_path):
    monkeypatch.setenv("MNEME_STUB_LOG", str(tmp_path / "stub.log"))
    return MempalaceRunner(binary=str(STUB))


def test_status_over_mixed_fixtures_matches_disk(tmp_path, monkeypatch):
    root = make_campaigns(tmp_path / "campaigns")
    report = conform.report(entity_for(root), runner=_runner(monkeypatch, tmp_path))

    by_campaign = {c: {r.dimension: r.state for r in report.for_campaign(c)} for c in
                   ("full", "ignore-only", "bare1", "bare2", "bare3")}
    # full has an authority → fully reported; the rest have none → missing_config
    assert by_campaign["full"]["recipe"] == State.CONFORMANT
    # no store pointer → the index is not checked (never an unscoped `sync`), and not "ok"
    assert by_campaign["full"]["index"] == State.INDEX_UNVERIFIED
    for bare in ("ignore-only", "bare1", "bare2", "bare3"):
        assert by_campaign[bare]["recipe"] == State.MISSING_CONFIG
    # reported state agrees with the silicon (FR-019 / SC-007)
    assert (root / "full" / ".mneme" / "mempalace.yaml").exists()
    assert not (root / "bare1" / ".mneme").exists()
    assert report.exit_code() == 0  # missing_config is not a failure


def test_status_flags_stale_index_and_stale_render(tmp_path, monkeypatch):
    root = make_campaigns(tmp_path / "campaigns")
    add_store_pointer(root)
    full = root / "full"
    # 1) the stub reports 3 drawers whose sources are missing (real `sync` report format)
    monkeypatch.setenv("MNEME_STUB_SYNC", "3,0")
    rn = _runner(monkeypatch, tmp_path)
    report = conform.report(entity_for(root), campaign="full", runner=rn)
    idx = next(r for r in report.for_campaign("full") if r.dimension == "index")
    assert idx.state == State.STALE
    assert "3 orphaned" in idx.note
    assert idx.ok  # stale only fails under --strict
    only_idx = conform.ConformanceReport(rows=(idx,))
    assert only_idx.exit_code() == 0 and only_idx.exit_code(strict=True) == 1

    # 2) hand-edit a derived wing file → stale-render FAIL (Principle V)
    (full / "docs" / "chapters" / "mempalace.yaml").write_text("wing: tampered\nrooms: []\n")
    rn2 = _runner(monkeypatch, tmp_path)
    report2 = conform.report(entity_for(root), campaign="full", runner=rn2)
    render_row = next(r for r in report2.for_campaign("full") if r.dimension == "render")
    assert render_row.state == State.STALE_RENDER and render_row.ok is False
    assert report2.exit_code() == 1


def _index(monkeypatch, tmp_path, mode):
    root = make_campaigns(tmp_path / "campaigns")
    add_store_pointer(root)
    monkeypatch.setenv("MNEME_STUB_SYNC", mode)
    rn = _runner(monkeypatch, tmp_path)
    report = conform.report(entity_for(root), campaign="full", runner=rn)
    return report, next(r for r in report.for_campaign("full") if r.dimension == "index")


def test_index_built_when_no_orphans_and_sync_targets_the_campaign_store(tmp_path, monkeypatch):
    _, idx = _index(monkeypatch, tmp_path, "0,0")
    assert idx.state == State.BUILT
    sync = [ln for ln in (tmp_path / "stub.log").read_text().splitlines() if " sync " in ln]
    assert sync and sync[0].startswith("--palace ")  # GH #22: campaign store, global opt first


def test_index_unverified_is_not_ok_shows_distinctly_and_only_strict_fails(tmp_path, monkeypatch):
    from mneme.mempalace import conform as c

    _, idx = _index(monkeypatch, tmp_path, "rc1")
    assert idx.state == State.INDEX_UNVERIFIED and "rc 1" in idx.note
    assert idx.ok is False  # the MCP surface reports ok:false
    flag = c.format_row(idx).split()[0]
    assert flag == "??"  # not "ok", not "FAIL"
    assert len(c.format_row(idx).split(idx.campaign)[0]) == 5  # same width as ok/FAIL flags
    only = conform.ConformanceReport(rows=(idx,))
    assert only.exit_code() == 0  # environmental: not a non-strict failure
    assert only.exit_code(strict=True) == 1  # strict: the index must be verified fresh


def test_sync_is_given_every_wing_root(tmp_path, monkeypatch):
    _index(monkeypatch, tmp_path, "0,0")
    sync = next(ln for ln in (tmp_path / "stub.log").read_text().splitlines() if " sync " in ln)
    assert " sync " in sync
    assert sync.index(" sync ") < sync.index("--root") < sync.index("--dry-run")


def test_out_of_scope_drawers_are_stale(tmp_path, monkeypatch):
    _, idx = _index(monkeypatch, tmp_path, "0,0,7")
    assert idx.state == State.STALE
    assert "7 drawers point outside" in idx.note and "mneme mp regenerate" in idx.note


def test_wing_outside_campaign_dir_is_passed_as_root(tmp_path, monkeypatch):
    root = make_campaigns(tmp_path / "campaigns")
    add_store_pointer(root)
    y = root / "full" / ".mneme" / "mempalace.yaml"
    ext = tmp_path / "ext"
    ext.mkdir()
    y.write_text(y.read_text().replace("source: docs/chapters", "source: ../../ext", 1))
    monkeypatch.setenv("MNEME_STUB_SYNC", "0,0")
    conform.report(entity_for(root), campaign="full", runner=_runner(monkeypatch, tmp_path))
    sync = next(ln for ln in (tmp_path / "stub.log").read_text().splitlines() if " sync " in ln)
    assert f"--root {root / 'full' / '../../ext'}" in sync
