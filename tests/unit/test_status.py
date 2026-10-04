"""T023 — honest status: drift, reachability, render-drift, exit codes."""

from __future__ import annotations

import subprocess

from hypostasis import render, status
from hypostasis.models import (
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
    target.write_text(f"# hypostasis-rendered; source-sha256: {digest}; do-not-edit\nkey: val\n")
    assert status.render_row(e, comp).ok


def test_render_stale_fails(tmp_path):
    e, comp, target = make_render_entity(tmp_path)
    target.write_text("# hypostasis-rendered; source-sha256: deadbeef; do-not-edit\nkey: val\n")
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


# ── declared embedder (GH #26) ────────────────────────────────────────────────

def _mp_entity(tmp_path, env):
    import dataclasses

    return dataclasses.replace(make_entity(tmp_path), env=env)


_FULL = {
    "MEMPALACE_BACKEND": "turbovec",
    "MEMPALACE_EMBEDDING_PROVIDER": "ollama",
    "MEMPALACE_EMBEDDING_MODEL": "qwen3-embedding:0.6b",
    "MEMPALACE_EMBEDDING_ENDPOINT": "http://192.0.2.10:11434",
}


def test_declared_embedder_accessor(tmp_path):
    from hypostasis.models import EmbedderDecl, declared_embedder

    assert declared_embedder(_mp_entity(tmp_path, {})) is None
    decl = declared_embedder(_mp_entity(tmp_path, _FULL))
    assert decl == EmbedderDecl("ollama", "qwen3-embedding:0.6b", "http://192.0.2.10:11434")


def test_embedder_row_ok_when_declared(tmp_path):
    row = status.embedder_row(_mp_entity(tmp_path, _FULL))
    assert row is not None and row.ok
    assert row.observed == "ollama:qwen3-embedding:0.6b @ http://192.0.2.10:11434"


def test_embedder_row_fails_when_undeclared_but_mempalace_in_play(tmp_path):
    row = status.embedder_row(_mp_entity(tmp_path, {"MEMPALACE_BACKEND": "turbovec"}))
    assert row is not None and not row.ok
    assert "384" in row.note and "MEMPALACE_EMBEDDING_" in row.note


def test_embedder_row_fails_when_incomplete(tmp_path):
    env = {"MEMPALACE_BACKEND": "turbovec", "MEMPALACE_EMBEDDING_PROVIDER": "ollama"}
    row = status.embedder_row(_mp_entity(tmp_path, env))
    assert row is not None and not row.ok


def test_embedder_row_onnx_needs_no_endpoint(tmp_path):
    env = {"MEMPALACE_EMBEDDING_PROVIDER": "onnx", "MEMPALACE_EMBEDDING_MODEL": "m",
           "MEMPALACE_BACKEND": "turbovec"}
    row = status.embedder_row(_mp_entity(tmp_path, env))
    assert row is not None and row.ok


def test_embedder_row_absent_without_mempalace(tmp_path):
    assert status.embedder_row(_mp_entity(tmp_path, {})) is None
    rows, _ = status.status_report(_mp_entity(tmp_path, {}), fake_runner("x"), lambda s: True)
    assert all(r.kind != "embedder" for r in rows)


def test_example_yaml_embedder_row_ok():
    import pathlib

    from hypostasis import config as cfg

    entity = cfg.load(pathlib.Path(__file__).resolve().parents[2] / "hypostasis.example.yaml")
    row = status.embedder_row(entity)
    assert row is not None and row.ok


def test_runner_for_entity_carries_embedder_env(tmp_path):
    from mneme.mempalace.runner import MempalaceRunner

    env = MempalaceRunner.for_entity(_mp_entity(tmp_path, _FULL)).env
    for k in ("MEMPALACE_EMBEDDING_PROVIDER", "MEMPALACE_EMBEDDING_MODEL",
              "MEMPALACE_EMBEDDING_ENDPOINT"):
        assert env[k] == _FULL[k]


def test_embedder_row_unknown_provider_fails(tmp_path):
    env = {**_FULL, "MEMPALACE_EMBEDDING_PROVIDER": "olama"}
    row = status.embedder_row(_mp_entity(tmp_path, env))
    assert row is not None and not row.ok
    assert "olama" in row.note and "openai-compat" in row.note


def test_embedder_provider_case_normalized(tmp_path):
    from hypostasis.models import declared_embedder

    env = {"MEMPALACE_BACKEND": "turbovec", "MEMPALACE_EMBEDDING_PROVIDER": "ONNX",
           "MEMPALACE_EMBEDDING_MODEL": "m"}
    row = status.embedder_row(_mp_entity(tmp_path, env))
    assert row is not None and row.ok
    env = {**_FULL, "MEMPALACE_EMBEDDING_PROVIDER": "Ollama"}
    assert declared_embedder(_mp_entity(tmp_path, env)).provider == "ollama"
