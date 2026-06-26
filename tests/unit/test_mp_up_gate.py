"""US4 unit tests (T024): `mneme up` store-health gate (FR-010) — fails, never brings up."""

from __future__ import annotations

import subprocess

import pytest

from hypostasis.models import Component, ConfigEntity, Machine, Order, Service, Source
from mneme import lifecycle
from mneme.mempalace import authority
from mneme.mempalace.models import CampaignMempalaceConfig, StorePointer, Wing


def _entity(tmp_path, campaign="oota"):
    (tmp_path / "campaigns" / campaign).mkdir(parents=True)
    cg = tmp_path / "cg"
    cg.mkdir()
    return ConfigEntity(
        venv=tmp_path / "venv",
        machines={"dgx": Machine("http://dgx:8001/v1")},
        services={"dgx": Service("dgx", "http://dgx:8001/v1", managed=False)},
        components={
            "CampaignGenerator": Component("CampaignGenerator", Source("path", str(cg)), "abc")
        },
        order=Order(install=("CampaignGenerator",), startup=("dgx",)),
        data_roots={"campaigns": tmp_path / "campaigns"},
    )


def _ok_runner():
    def run(cmd, env):
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    return run


def test_up_fails_when_store_gate_reports_not_ready(tmp_path):
    e = _entity(tmp_path)
    with pytest.raises(lifecycle.LifecycleError) as ei:
        lifecycle.up(
            e, "oota", prober=lambda s: True, runner=_ok_runner(), render=False,
            store_gate=lambda cdir: "no store at ...",
        )
    assert "not brought up" in str(ei.value) and "mneme mp bringup" in str(ei.value)


def test_up_proceeds_when_store_healthy(tmp_path):
    e = _entity(tmp_path)
    res = lifecycle.up(
        e, "oota", prober=lambda s: True, runner=_ok_runner(), render=False,
        store_gate=lambda cdir: None,  # healthy
    )
    assert res.rc == 0


def test_mempalace_not_ready_logic(tmp_path):
    # no .mneme authority → not gated (pre-003 campaign)
    camp = tmp_path / "campaigns" / "oota"
    camp.mkdir(parents=True)
    assert lifecycle.mempalace_not_ready(camp) is None
    # authority with a store pointer, but the store is missing → a reason
    store = tmp_path / "store"
    cfg = CampaignMempalaceConfig(
        campaign="oota", recipe_version="1.0.0",
        wings=(Wing("oota", ".", "reference", ()),), store=StorePointer("oota", store),
    )
    authority.write(cfg, camp)
    reason = lifecycle.mempalace_not_ready(camp)
    assert reason and "no store" in reason
