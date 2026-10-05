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


# ── dev mode (FR-004 amendment, 2026-10-05) ───────────────────────────────────

import json  # noqa: E402


def dev_entity(tmp_path, pin=""):
    e = make_entity(tmp_path, pin=pin)
    return ConfigEntity(
        venv=e.venv, machines=e.machines, services=e.services,
        components=e.components, order=e.order, mode="dev",
    )


def fake_dist(venv, name, url, editable):
    d = venv / "lib" / "python3.12" / "site-packages" / f"{name}-0.1.dist-info"
    d.mkdir(parents=True)
    (d / "direct_url.json").write_text(
        json.dumps({"url": url, "dir_info": {"editable": editable}})
    )


def git_runner(head, porcelain=""):
    def run(cmd):
        out = porcelain if "status" in cmd else head + "\n"
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

    return run


def test_dev_component_editable_ok(tmp_path):
    e = dev_entity(tmp_path)
    src = (tmp_path / "src")
    src.mkdir()
    fake_dist(e.venv, "comp", src.resolve().as_uri(), True)
    row = status.component_row(e.components["comp"], git_runner("abcdef1234567890"), e)
    assert row.ok
    assert row.observed == "editable @ abcdef123456"
    assert row.expected == "editable (dev mode)"


def test_dev_component_dirty_marker_and_pin_note(tmp_path):
    e = dev_entity(tmp_path, pin="1234567890abcdef")
    src = tmp_path / "src"
    src.mkdir()
    fake_dist(e.venv, "comp", src.resolve().as_uri(), True)
    row = status.component_row(e.components["comp"], git_runner("abcdef1234567890", " M x.py\n"), e)
    assert row.ok
    assert row.observed.endswith("(+dirty)")
    assert "pin 1234567890ab (not enforced in dev mode)" in row.note


def test_dev_component_non_editable_install_fails(tmp_path):
    e = dev_entity(tmp_path)
    src = tmp_path / "src"
    src.mkdir()
    fake_dist(e.venv, "comp", src.resolve().as_uri(), False)
    row = status.component_row(e.components["comp"], git_runner("abcdef1234567890"), e)
    assert not row.ok
    assert "non-editable" in row.note and "hypostasis install" in row.note


def test_dev_component_installed_from_elsewhere_fails(tmp_path):
    e = dev_entity(tmp_path)
    (tmp_path / "src").mkdir()
    fake_dist(e.venv, "comp", "file:///somewhere/else", True)
    row = status.component_row(e.components["comp"], git_runner("abcdef1234567890"), e)
    assert not row.ok
    assert "file:///somewhere/else" in row.note


def test_dev_component_not_installed_fails(tmp_path):
    e = dev_entity(tmp_path)
    row = status.component_row(e.components["comp"], git_runner("abcdef1234567890"), e)
    assert not row.ok and "not installed" in row.note


def test_pinned_mode_unchanged_with_entity(tmp_path):
    e = make_entity(tmp_path, pin="abc123def456")
    row = status.component_row(e.components["comp"], fake_runner("abc123def456"), e)
    assert row.ok and row.expected == "abc123def456"


# ── review fixes: pinned-mode leftovers, URL matching, purelib, legacy, non-git ──

def venv_runner(venv, head="abcdef1234567890", porcelain="", git=True):
    """Answers purelib from the venv's lib/python*/ named by pyvenv.cfg-less `live` dir."""
    live = venv / "lib" / "python3.12" / "site-packages"

    def run(cmd):
        if cmd[0].endswith("python"):
            return subprocess.CompletedProcess(cmd, 0, stdout=str(live) + "\n", stderr="")
        if not git:
            return subprocess.CompletedProcess(cmd, 128, stdout="", stderr="no")
        out = porcelain if "status" in cmd else head + "\n"
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

    return run


def pinned_entity(tmp_path, pin="abc123def456"):
    return make_entity(tmp_path, pin=pin)


def test_pinned_mode_fails_on_leftover_editable_install(tmp_path):
    e = pinned_entity(tmp_path)
    src = tmp_path / "src"
    src.mkdir()
    fake_dist(e.venv, "comp", src.resolve().as_uri(), True)
    row = status.component_row(e.components["comp"], venv_runner(e.venv, "abc123def456"), e)
    assert not row.ok
    assert "installed editable but mode is pinned" in row.note


def test_pinned_mode_non_editable_keeps_pin_check(tmp_path):
    e = pinned_entity(tmp_path)
    src = tmp_path / "src"
    src.mkdir()
    fake_dist(e.venv, "comp", src.resolve().as_uri(), False)
    ok = status.component_row(e.components["comp"], venv_runner(e.venv, "abc123def456"), e)
    assert ok.ok
    bad = status.component_row(e.components["comp"], venv_runner(e.venv, "9999feedface"), e)
    assert not bad.ok and "drift" in bad.note


def test_pinned_mode_not_installed_unchanged(tmp_path):
    e = pinned_entity(tmp_path)
    row = status.component_row(e.components["comp"], venv_runner(e.venv, "abc123def456"), e)
    assert row.ok


def test_url_match_symlinked_parent(tmp_path):
    real = tmp_path / "real"
    (real / "src").mkdir(parents=True)
    link = tmp_path / "link"
    link.symlink_to(real)
    e = make_entity(link)  # locator is under the symlink
    e = ConfigEntity(venv=tmp_path / "venv", machines=e.machines, services=e.services,
                     components=e.components, order=e.order, mode="dev")
    # pip records the UN-resolved abspath
    fake_dist(e.venv, "comp", (link / "src").as_uri(), True)
    row = status.component_row(e.components["comp"], venv_runner(e.venv), e)
    assert row.ok, row.note


def test_url_match_percent_encoding_and_trailing_slash(tmp_path):
    spaced = tmp_path / "my src"
    spaced.mkdir()
    comp = Component("comp", Source("path", str(spaced)), "")
    e = ConfigEntity(venv=tmp_path / "venv", machines={}, services={}, components={"comp": comp},
                     order=Order(install=("comp",), startup=()), mode="dev")
    fake_dist(e.venv, "comp", spaced.as_uri() + "/", True)  # %20 and trailing slash
    assert "%20" in spaced.as_uri()
    assert status.component_row(comp, venv_runner(e.venv), e).ok


def test_only_live_purelib_counts(tmp_path):
    e = dev_entity(tmp_path)
    src = tmp_path / "src"
    src.mkdir()
    stale = e.venv / "lib" / "python3.11" / "site-packages" / "comp-0.1.dist-info"
    stale.mkdir(parents=True)
    (stale / "direct_url.json").write_text(
        json.dumps({"url": src.resolve().as_uri(), "dir_info": {"editable": True}}))
    fake_dist(e.venv, "comp", src.resolve().as_uri(), False)  # live 3.12: non-editable
    row = status.component_row(e.components["comp"], venv_runner(e.venv), e)
    assert not row.ok and "non-editable" in row.note


def test_purelib_falls_back_to_pyvenv_cfg(tmp_path):
    e = dev_entity(tmp_path)
    src = tmp_path / "src"
    src.mkdir()
    (e.venv).mkdir(parents=True)
    (e.venv / "pyvenv.cfg").write_text("home = /usr\nversion = 3.12.3\n")
    stale = e.venv / "lib" / "python3.11" / "site-packages" / "comp-0.1.dist-info"
    stale.mkdir(parents=True)
    (stale / "direct_url.json").write_text(
        json.dumps({"url": src.resolve().as_uri(), "dir_info": {"editable": True}}))
    (e.venv / "lib" / "python3.12" / "site-packages").mkdir(parents=True)
    row = status.component_row(e.components["comp"], git_runner("abcdef1234567890"), e)
    assert not row.ok  # interpreter "can't run" (fake), cfg says 3.12, which has nothing


def test_legacy_egg_link_and_pth_accepted(tmp_path):
    e = dev_entity(tmp_path)
    src = tmp_path / "src"
    src.mkdir()
    sp = e.venv / "lib" / "python3.12" / "site-packages"
    sp.mkdir(parents=True)
    (sp / "comp.egg-link").write_text(f"{src}\n.\n")
    row = status.component_row(e.components["comp"], venv_runner(e.venv), e)
    assert row.ok and "legacy" in row.observed
    (sp / "comp.egg-link").unlink()
    (sp / "easy-install.pth").write_text(f"import sys\n{src}\n")
    row = status.component_row(e.components["comp"], venv_runner(e.venv), e)
    assert row.ok and "legacy" in row.observed


def test_dev_non_git_source_ok_depends_on_install(tmp_path):
    e = dev_entity(tmp_path)
    src = tmp_path / "src"
    src.mkdir()
    bad = status.component_row(e.components["comp"], venv_runner(e.venv, git=False), e)
    assert not bad.ok and bad.observed == "editable @ (no git)"
    fake_dist(e.venv, "comp", src.resolve().as_uri(), True)
    good = status.component_row(e.components["comp"], venv_runner(e.venv, git=False), e)
    assert good.ok and good.observed == "editable @ (no git)"


# ── confirmation-review fixes: src layout, marker kinds, precedence, relative .pth ──

def _sp(e):
    sp = e.venv / "lib" / "python3.12" / "site-packages"
    sp.mkdir(parents=True, exist_ok=True)
    return sp


def test_legacy_src_layout_accepted(tmp_path):
    e = dev_entity(tmp_path)
    (tmp_path / "src" / "src").mkdir(parents=True)
    (_sp(e) / "comp.egg-link").write_text(f"{tmp_path / 'src' / 'src'}\n.\n")
    row = status.component_row(e.components["comp"], venv_runner(e.venv), e)
    assert row.ok and "legacy" in row.observed
    (_sp(e) / "comp.egg-link").unlink()
    (_sp(e) / "easy-install.pth").write_text(f"{tmp_path / 'src' / 'src'}\n")
    assert status.component_row(e.components["comp"], venv_runner(e.venv), e).ok


def test_unrelated_pth_is_not_an_editable_marker(tmp_path):
    (tmp_path / "src").mkdir()
    e = dev_entity(tmp_path)
    (_sp(e) / "foo.pth").write_text(f"{tmp_path / 'src'}\n")
    assert not status.component_row(e.components["comp"], venv_runner(e.venv), e).ok
    p = pinned_entity(tmp_path)
    row = status.component_row(p.components["comp"], venv_runner(p.venv, "abc123def456"), p)
    assert row.ok  # no false "installed editable but mode is pinned"


def test_dist_elsewhere_beats_stale_legacy_marker(tmp_path):
    e = dev_entity(tmp_path)
    (tmp_path / "src").mkdir()
    fake_dist(e.venv, "comp", "file:///somewhere/else", False)
    (_sp(e) / "easy-install.pth").write_text(f"{tmp_path / 'src'}\n")
    state = status.install_state(e.venv, e.components["comp"], venv_runner(e.venv))
    assert state[0] == "elsewhere"
    assert not status.component_row(e.components["comp"], venv_runner(e.venv), e).ok


def test_relative_pth_resolves_against_site_packages_not_cwd(tmp_path, monkeypatch):
    e = dev_entity(tmp_path)
    src = tmp_path / "src"
    src.mkdir()
    (_sp(e) / "easy-install.pth").write_text(".\n")
    monkeypatch.chdir(src)
    state = status.install_state(e.venv, e.components["comp"], venv_runner(e.venv))
    assert state[0] == "absent"


def test_dev_row_spawns_interpreter_once(tmp_path):
    e = dev_entity(tmp_path)
    (tmp_path / "src").mkdir()
    base = venv_runner(e.venv)
    calls = []

    def counting(cmd):
        calls.append(cmd)
        return base(cmd)

    status.component_row(e.components["comp"], counting, e)
    assert sum(1 for c in calls if c[0].endswith("python")) == 1
