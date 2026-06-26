"""US4 integration test (T036): bootstrap a bare campaign, then refresh builds its index."""

from __future__ import annotations

from mneme.mempalace import authority, bootstrap, recipe, refresh
from mneme.mempalace.runner import MempalaceRunner
from tests.fixtures import STUB, entity_for, make_campaigns


def test_bootstrap_then_refresh_builds_index(tmp_path, monkeypatch):
    root = make_campaigns(tmp_path / "campaigns")
    bare = root / "bare1"
    assert not authority.has_authority(bare)

    # bootstrap writes the starter authority + renders directly into the campaign dir
    # (creation-time write; for an existing-campaign upgrade this would go via workcopy)
    cfg = bootstrap.starter_config("bare1", bare, recipe.current())
    bootstrap.write_into(cfg, recipe.current(), bare)
    assert authority.has_authority(bare)

    # a subsequent refresh now finds a wing (the rendered root mempalace.yaml) and mines it
    monkeypatch.setenv("MNEME_STUB_LOG", str(tmp_path / "stub.log"))
    runner = MempalaceRunner(binary=str(STUB))
    results = {r.campaign: r for r in refresh.refresh(entity_for(root), runner=runner)}
    assert results["bare1"].skipped is False and not results["bare1"].failed
    assert results["bare1"].wings  # at least the root wing was mined
