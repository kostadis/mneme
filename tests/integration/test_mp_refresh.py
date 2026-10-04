"""US1 integration test (T014): discover→refresh --all via the recording stub binary."""

from __future__ import annotations

import pytest

from mneme.mempalace import refresh
from mneme.mempalace.runner import MempalaceRunner
from tests.fixtures import STUB, add_store_pointer, entity_for, make_campaigns, with_onnx


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    """Keep derived palace paths (~/.mempalace/palaces/<alias>) inside tmp_path."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

def _runner_and_log(tmp_path, monkeypatch):
    log = tmp_path / "stub.log"
    monkeypatch.setenv("MNEME_STUB_LOG", str(log))
    return MempalaceRunner(binary=str(STUB)), log


def test_refresh_all_mines_full_and_skips_bare(tmp_path, monkeypatch):
    root = make_campaigns(tmp_path / "campaigns")
    add_store_pointer(root)
    runner, log = _runner_and_log(tmp_path, monkeypatch)
    results = {r.campaign: r for r in refresh.refresh(entity_for(root), runner=runner)}

    assert not results["full"].failed and not results["full"].skipped
    assert results["bare1"].skipped and results["bare2"].skipped and results["bare3"].skipped

    lines = log.read_text().splitlines()
    toks = [ln.split() for ln in lines if "mine" in ln.split()]
    mined = [t[t.index("mine") + 1] for t in toks]
    # sub-scopes mined before the campaign root
    assert any(p.endswith("docs/chapters") for p in mined)
    chap = next(i for i, p in enumerate(mined) if p.endswith("docs/chapters"))
    rootw = next(i for i, p in enumerate(mined) if p == str(root / "full"))
    assert chap < rootw


def test_refresh_is_idempotent(tmp_path, monkeypatch):
    root = make_campaigns(tmp_path / "campaigns")
    add_store_pointer(root)
    runner, _ = _runner_and_log(tmp_path, monkeypatch)
    first = refresh.refresh(with_onnx(entity_for(root)), campaign="full", runner=runner)
    second = refresh.refresh(with_onnx(entity_for(root)), campaign="full", runner=runner)
    assert not first[0].failed and not second[0].failed
    assert first[0].wings == second[0].wings  # same wings, no error on re-run
