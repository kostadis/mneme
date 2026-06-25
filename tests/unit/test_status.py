"""T023 — honest status: drift, reachability, render-drift, exit codes."""

from __future__ import annotations

import subprocess

from mneme import render, status
from mneme.models import (
    Component,
    ConfigEntity,
    Health,
    Machine,
    Order,
    Service,
    Source,
)


def fake_runner(head: str, rc: int = 0):
    def run(cmd):
        return subprocess.CompletedProcess(
            cmd, rc, stdout=(head + "\n") if rc == 0 else "", stderr=""
        )

    return run


def make_entity(tmp_path, pin="abc123def456"):
    endpoint = "http://dgx:8001/v1"
    comp = Component("comp", Source("path", str(tmp_path / "src")), pin)
    return ConfigEntity(
        venv=tmp_path / "venv",
        machines={"dgx": Machine(endpoint)},
        services={
            "dgx": Service("dgx", endpoint, managed=False, health=Health("http", "/models"))
        },
        components={"comp": comp},
        order=Order(install=("comp",), startup=("dgx",)),
    )


# ── component drift (source HEAD vs pin) ──────────────────────────────────────

def test_component_at_pin_passes(tmp_path):
    e = make_entity(tmp_path, pin="abc123def456")
    row = status.component_row(e.components["comp"], fake_runner("abc123def456"))
    assert row.ok
    assert row.observed.startswith("abc123")


def test_component_source_drifted_fails(tmp_path):
    e = make_entity(tmp_path, pin="abc123def456")
    row = status.component_row(e.components["comp"], fake_runner("9999feedface"))
    assert not row.ok
    assert "drift" in row.note.lower()


def test_component_not_a_repo_fails(tmp_path):
    e = make_entity(tmp_path, pin="abc123def456")
    row = status.component_row(e.components["comp"], fake_runner("", rc=1))
    assert not row.ok
    assert "not a git repo" in row.note


# ── service reachability ──────────────────────────────────────────────────────

def test_service_reachable_passes(tmp_path):
    e = make_entity(tmp_path)
    row = status.service_row("dgx", e.services["dgx"], prober=lambda s: True)
    assert row.ok and row.observed == "reachable"


def test_service_unreachable_fails(tmp_path):
    e = make_entity(tmp_path)
    row = status.service_row("dgx", e.services["dgx"], prober=lambda s: False)
    assert not row.ok and "UNREACHABLE" in row.observed


# ── render drift (stamped hash vs current authority) ──────────────────────────

def make_render_entity(tmp_path, endpoint="http://dgx:8001/v1"):
    target = tmp_path / "wiring.yaml"
    comp = Component(
        "cg", Source("path", str(tmp_path / "src")), "abc123",
        config_template="x.j2", config_target=target,
    )
    e = ConfigEntity(
        venv=tmp_path / "venv",
        machines={"dgx": Machine(endpoint)},
        services={},
        components={"cg": comp},
        order=Order(install=("cg",), startup=()),
    )
    return e, comp, target


def test_render_in_sync_passes(tmp_path):
    e, comp, target = make_render_entity(tmp_path)
    digest = render.subtree_sha256(render.component_context(e, comp))
    target.write_text(f"# mneme-rendered; source-sha256: {digest}; do-not-edit\nkey: val\n")
    assert status.render_row(e, comp).ok


def test_render_stale_fails(tmp_path):
    e, comp, target = make_render_entity(tmp_path)
    target.write_text("# mneme-rendered; source-sha256: deadbeef; do-not-edit\nkey: val\n")
    row = status.render_row(e, comp)
    assert not row.ok and "stale" in row.note


def test_render_missing_fails(tmp_path):
    e, comp, _ = make_render_entity(tmp_path)
    row = status.render_row(e, comp)
    assert not row.ok and "missing" in row.note


# ── overall report + exit code ────────────────────────────────────────────────

def test_report_all_pass_exit_0(tmp_path):
    e = make_entity(tmp_path, pin="abc123def456")
    rows, code = status.status_report(
        e, runner=fake_runner("abc123def456"), prober=lambda s: True
    )
    assert code == 0 and all(r.ok for r in rows)


def test_report_any_fail_exit_1(tmp_path):
    e = make_entity(tmp_path, pin="abc123def456")
    # component at pin, but the service is unreachable → red dashboard exits red
    rows, code = status.status_report(
        e, runner=fake_runner("abc123def456"), prober=lambda s: False
    )
    assert code == 1
