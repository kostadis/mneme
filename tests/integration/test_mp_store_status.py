"""US2 integration (T014/T015): a brought-up campaign is observable — store + backup +
faces dimensions in status, built/conformant, matching disk."""

from __future__ import annotations

from mneme.mempalace import bringup, conform
from mneme.mempalace.models import State
from mneme.mempalace.runner import MempalaceRunner
from tests.fixtures import STUB, entity_for, make_greenfield_campaign


def _bring_up(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("MNEME_STUB_LOG", str(tmp_path / "stub.log"))
    runner = MempalaceRunner(binary=str(STUB))
    root = tmp_path / "campaigns"
    make_greenfield_campaign(root, "stormhaven")
    entity = entity_for(root)
    bringup.bringup(entity, "stormhaven", runner=runner, do_backup=True)
    return entity, runner


def test_status_shows_store_and_faces_built(tmp_path, monkeypatch):
    entity, runner = _bring_up(tmp_path, monkeypatch)
    report = conform.report(entity, "stormhaven", runner=runner)
    dims = {r.dimension: r.state for r in report.for_campaign("stormhaven")}
    assert dims["recipe"] == State.CONFORMANT
    assert dims["store"] == State.BUILT  # healthy turbovec store
    assert dims["faces"] == State.CONFORMANT  # right store everywhere (SC-008)
    assert "backup" in dims  # backup dimension surfaced
    assert report.exit_code() == 0  # all green after bring-up


def test_status_backup_dimension_reflects_disk(tmp_path, monkeypatch):
    entity, runner = _bring_up(tmp_path, monkeypatch)
    report = conform.report(entity, "stormhaven", runner=runner)
    backup_row = next(r for r in report.for_campaign("stormhaven") if r.dimension == "backup")
    assert "backup:" in backup_row.note  # bring-up took an initial backup (do_backup=True)
