"""US2 integration test (T018): honest status over mixed fixtures via the stub binary."""

from __future__ import annotations

from mneme.mempalace import conform
from mneme.mempalace.models import State
from mneme.mempalace.runner import MempalaceRunner
from tests.fixtures import STUB, entity_for, make_campaigns


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
    assert by_campaign["full"]["index"] == State.BUILT
    for bare in ("ignore-only", "bare1", "bare2", "bare3"):
        assert by_campaign[bare]["recipe"] == State.MISSING_CONFIG
    # reported state agrees with the silicon (FR-019 / SC-007)
    assert (root / "full" / ".mneme" / "mempalace.yaml").exists()
    assert not (root / "bare1" / ".mneme").exists()
    assert report.exit_code() == 0  # missing_config is not a failure


def test_status_flags_stale_index_and_stale_render(tmp_path, monkeypatch):
    root = make_campaigns(tmp_path / "campaigns")
    full = root / "full"
    # 1) simulate source-vs-index drift for the stub
    (full / ".stub_drift").touch()
    rn = _runner(monkeypatch, tmp_path)
    report = conform.report(entity_for(root), campaign="full", runner=rn)
    idx = next(r for r in report.for_campaign("full") if r.dimension == "index")
    assert idx.state == State.STALE
    assert report.exit_code() == 0  # stale only fails under --strict
    assert report.exit_code(strict=True) == 1

    # 2) hand-edit a derived wing file → stale-render FAIL (Principle V)
    (full / "docs" / "chapters" / "mempalace.yaml").write_text("wing: tampered\nrooms: []\n")
    rn2 = _runner(monkeypatch, tmp_path)
    report2 = conform.report(entity_for(root), campaign="full", runner=rn2)
    render_row = next(r for r in report2.for_campaign("full") if r.dimension == "render")
    assert render_row.state == State.STALE_RENDER and render_row.ok is False
    assert report2.exit_code() == 1
