"""mneme per-campaign lifecycle — gate deps, build the CG launch, up/down."""

from __future__ import annotations

import subprocess

import pytest

from hypostasis.models import (
    Component,
    ConfigEntity,
    Health,
    Machine,
    Order,
    Service,
    Source,
)
from mneme import lifecycle


def fake_runner(rc: int = 0):
    calls: list = []

    def run(cmd, env):
        calls.append((cmd, env))
        return subprocess.CompletedProcess(cmd, rc, stdout="", stderr="boom" if rc else "")

    run.calls = calls
    return run


def all_up(_service):
    return True


def make_entity(tmp_path, campaign="oota", make_campaign=True):
    camp_root = tmp_path / "campaigns"
    if make_campaign:
        (camp_root / campaign).mkdir(parents=True)
    cg = tmp_path / "cg"
    cg.mkdir(exist_ok=True)
    return ConfigEntity(
        venv=tmp_path / "venv",
        machines={"dgx": Machine("http://dgx:8001/v1")},
        services={
            "dgx": Service("dgx", "http://dgx:8001/v1", managed=False, health=Health("http", "/m")),
            "rpg_lib": Service(
                "rpg_lib", "http://localhost:8000", managed=False, health=Health("http", "/")
            ),
        },
        components={
            "CampaignGenerator": Component("CampaignGenerator", Source("path", str(cg)), "abc123")
        },
        order=Order(install=("CampaignGenerator",), startup=("dgx", "rpg_lib")),
        data_roots={"campaigns": camp_root},
        env={"MEMPALACE_BACKEND": "turbovec"},
    )


def test_up_dry_run_builds_launch(tmp_path):
    e = make_entity(tmp_path)
    res = lifecycle.up(e, "oota", prober=all_up, render=False, dry_run=True)
    assert res.dry_run and res.rc is None
    assert res.command[0].endswith("/cg/start")
    assert "--campaign-dir" in res.command and "--port" in res.command
    assert str(tmp_path / "campaigns" / "oota") in res.command
    assert res.env_exported == ["MEMPALACE_BACKEND"]


def test_up_gates_on_unreachable_substrate(tmp_path):
    e = make_entity(tmp_path)

    def dgx_down(s):
        return s.name != "dgx"

    with pytest.raises(lifecycle.LifecycleError) as ei:
        lifecycle.up(e, "oota", prober=dgx_down, render=False)
    assert "substrate not ready" in str(ei.value) and "dgx" in str(ei.value)


def test_up_campaign_not_found(tmp_path):
    e = make_entity(tmp_path, make_campaign=False)
    with pytest.raises(lifecycle.LifecycleError) as ei:
        lifecycle.up(e, "oota", prober=all_up, render=False)
    assert "campaign workspace not found" in str(ei.value)


def test_up_starts_cg_with_env(tmp_path):
    e = make_entity(tmp_path)
    runner = fake_runner(rc=0)
    res = lifecycle.up(e, "oota", port=5050, prober=all_up, runner=runner, render=False)
    assert res.rc == 0
    cmd, env = runner.calls[0]
    assert "5050" in cmd
    assert env["MEMPALACE_BACKEND"] == "turbovec"  # hypostasis env exported into CG


def test_up_fails_loud_when_start_fails(tmp_path):
    e = make_entity(tmp_path)
    with pytest.raises(lifecycle.LifecycleError) as ei:
        lifecycle.up(e, "oota", prober=all_up, runner=fake_runner(rc=1), render=False)
    assert "start failed" in str(ei.value)


def test_down_invokes_cg_stop(tmp_path):
    e = make_entity(tmp_path)
    runner = fake_runner(rc=0)
    lifecycle.down(e, "oota", port=5050, runner=runner)
    cmd, _ = runner.calls[0]
    assert cmd[0].endswith("/cg/stop") and "5050" in cmd


def test_down_fails_loud(tmp_path):
    e = make_entity(tmp_path)
    with pytest.raises(lifecycle.LifecycleError):
        lifecycle.down(e, "oota", runner=fake_runner(rc=1))
