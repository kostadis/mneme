"""T008 — validation of the single authority (mneme.yaml)."""

from __future__ import annotations

import pytest
import yaml

from mneme import config as cfg


def valid_raw(tmp_path) -> dict:
    """A minimal, valid authority. Paths are absolute (under tmp_path)."""
    return {
        "venv": str(tmp_path / "venv"),
        "machines": {"dgx": {"endpoint": "http://dgx:8001/v1", "default_model": "m"}},
        "data_roots": {"fivetools": str(tmp_path / "data")},
        "services": {
            "dgx": {"url": "http://dgx:8001/v1", "managed": False},
            "svc": {
                "url": "http://localhost:9",
                "port": 9,
                "managed": True,
                "start": "start-it",
                "stop": "stop-it",
            },
        },
        "components": {
            "comp": {"source": {"path": str(tmp_path / "src")}, "pin": "abc1234"},
        },
        "order": {"install": ["comp"], "startup": ["dgx", "svc"]},
    }


def write(tmp_path, raw) -> str:
    path = tmp_path / "mneme.yaml"
    path.write_text(yaml.safe_dump(raw))
    return str(path)


def load_raw(tmp_path, raw):
    return cfg.load(write(tmp_path, raw))


def assert_problem(tmp_path, raw, needle: str):
    with pytest.raises(cfg.ConfigError) as ei:
        load_raw(tmp_path, raw)
    assert any(needle in p for p in ei.value.problems), ei.value.problems


def test_valid_config_loads(tmp_path):
    entity = load_raw(tmp_path, valid_raw(tmp_path))
    assert entity.venv.is_absolute()
    assert "dgx" in entity.machines
    assert entity.order.install == ("comp",)
    assert entity.components["comp"].source.kind == "path"


def test_missing_required_field(tmp_path):
    raw = valid_raw(tmp_path)
    del raw["venv"]
    assert_problem(tmp_path, raw, "venv")


def test_dangling_order_reference(tmp_path):
    raw = valid_raw(tmp_path)
    raw["order"]["install"] = ["does-not-exist"]
    assert_problem(tmp_path, raw, "not a declared component")


def test_duplicate_in_order_rejected(tmp_path):
    # order.* is a total order; a name listed twice is contradictory (acyclicity guard).
    raw = valid_raw(tmp_path)
    raw["order"]["install"] = ["comp", "comp"]
    assert_problem(tmp_path, raw, "appears more than once")


def test_range_pin_rejected(tmp_path):
    raw = valid_raw(tmp_path)
    raw["components"]["comp"]["pin"] = ">=1.0"
    assert_problem(tmp_path, raw, "range/editable")


def test_editable_pin_rejected(tmp_path):
    raw = valid_raw(tmp_path)
    raw["components"]["comp"]["pin"] = "-e ."
    assert_problem(tmp_path, raw, "range/editable")


def test_second_authority_rejected(tmp_path):
    # A lockfile pointer would be a second writable authority (Principle V).
    raw = valid_raw(tmp_path)
    raw["lockfile"] = str(tmp_path / "mneme.lock")
    assert_problem(tmp_path, raw, "forbidden field 'lockfile'")


def test_managed_service_requires_start_stop(tmp_path):
    raw = valid_raw(tmp_path)
    del raw["services"]["svc"]["stop"]
    assert_problem(tmp_path, raw, "requires both 'start' and 'stop'")


def test_config_template_requires_target(tmp_path):
    raw = valid_raw(tmp_path)
    raw["components"]["comp"]["config_template"] = "x.j2"  # no config_target
    assert_problem(tmp_path, raw, "config_target missing")


def test_all_problems_reported_at_once(tmp_path):
    raw = valid_raw(tmp_path)
    del raw["venv"]
    raw["order"]["install"] = ["nope"]
    with pytest.raises(cfg.ConfigError) as ei:
        load_raw(tmp_path, raw)
    assert len(ei.value.problems) >= 2


def test_env_scalars_parse_and_coerce_to_str(tmp_path):
    raw = valid_raw(tmp_path)
    raw["env"] = {"MEMPALACE_BACKEND": "turbovec", "N": 1, "FLAG": True}
    entity = load_raw(tmp_path, raw)
    assert entity.env == {"MEMPALACE_BACKEND": "turbovec", "N": "1", "FLAG": "True"}


def test_env_nonscalar_value_rejected(tmp_path):
    raw = valid_raw(tmp_path)
    raw["env"] = {"BAD": {"nested": "map"}}
    assert_problem(tmp_path, raw, "must be a scalar")


def test_repo_mneme_yaml_is_valid():
    """The real authority shipped in the repo must validate."""
    import pathlib

    repo_root = pathlib.Path(__file__).resolve().parents[2]
    entity = cfg.load(repo_root / "mneme.yaml")
    # six in-scope components + claudelib (shared library dep)
    assert len(entity.components) == 7
    assert entity.order.install[0] == "dgxlib"
    # claudelib is a pure library: installed, no rendered config, no service entry
    assert "claudelib" in entity.components
    assert entity.components["claudelib"].config_template is None
    assert "claudelib" not in entity.services
    # every order name resolves; every managed service has start/stop (validated on load)
    assert entity.services["dgx"].managed is False
    # env-wiring present (mempalace backend)
    assert entity.env.get("MEMPALACE_BACKEND") == "turbovec"
