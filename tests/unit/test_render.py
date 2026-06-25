"""T009 — golden-file render + source-hash stamp + drift detection."""

from __future__ import annotations

from pathlib import Path

import yaml

from mneme import config as cfg
from mneme import render as rnd


def make_config(tmp_path, endpoint="http://192.0.2.10:8001/v1"):
    tmp_path = Path(tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    target = tmp_path / "out" / "models.yaml"
    raw = {
        "venv": str(tmp_path / "venv"),
        "machines": {"dgx": {"endpoint": endpoint, "default_model": "Qwen-X"}},
        "data_roots": {"fivetools": str(tmp_path / "data")},
        "services": {
            "dgx": {"url": endpoint, "managed": False},
            "turbovecdb": {
                "url": "http://127.0.0.1:8077",
                "port": 8077,
                "managed": True,
                "start": "s",
                "stop": "t",
            },
        },
        "components": {
            "dgxlib": {
                "source": {"path": str(tmp_path / "dgx")},
                "pin": "deadbeef",
                "config_template": "dgxlib.models.yaml.j2",
                "config_target": str(target),
            },
        },
        "order": {"install": ["dgxlib"], "startup": ["dgx", "turbovecdb"]},
    }
    path = tmp_path / "mneme.yaml"
    path.write_text(yaml.safe_dump(raw))
    return cfg.load(path), target


def test_render_emits_expected_values(tmp_path):
    entity, _ = make_config(tmp_path)
    derived = rnd.render_component(entity, entity.components["dgxlib"])
    assert derived is not None
    data = yaml.safe_load(derived.content)
    assert data["endpoint"] == "http://192.0.2.10:8001/v1"
    assert data["default_model"] == "Qwen-X"
    assert data["venv"] == str(entity.venv)


def test_stamp_written_and_readback_matches(tmp_path):
    entity, target = make_config(tmp_path)
    derived = rnd.render_component(entity, entity.components["dgxlib"])
    written = rnd.write_rendered(derived)
    assert written == target
    # header is present and parseable
    first_line = target.read_text().splitlines()[0]
    assert first_line.startswith(rnd.STAMP_PREFIX)
    assert rnd.read_stamp(target) == derived.source_sha256
    # the body below the header is still valid YAML
    body = "\n".join(target.read_text().splitlines()[1:])
    assert yaml.safe_load(body)["endpoint"].endswith("/v1")


def test_hash_is_deterministic(tmp_path):
    entity, _ = make_config(tmp_path)
    a = rnd.render_component(entity, entity.components["dgxlib"])
    b = rnd.render_component(entity, entity.components["dgxlib"])
    assert a.source_sha256 == b.source_sha256


def test_drift_detected_on_value_change(tmp_path):
    """Changing a consumed value changes the stamp — the basis of drift detection."""
    e1, _ = make_config(tmp_path / "a", endpoint="http://192.0.2.10:8001/v1")
    e2, _ = make_config(tmp_path / "b", endpoint="http://10.0.0.9:8001/v1")
    h1 = rnd.render_component(e1, e1.components["dgxlib"]).source_sha256
    h2 = rnd.render_component(e2, e2.components["dgxlib"]).source_sha256
    assert h1 != h2


def test_render_all_skips_templateless_components(tmp_path):
    entity, _ = make_config(tmp_path)
    derived = rnd.render_all(entity)
    assert [d.component for d in derived] == ["dgxlib"]


def test_repo_templates_all_render():
    """Every component template in the repo authority renders without error."""
    import pathlib

    repo_root = pathlib.Path(__file__).resolve().parents[2]
    entity = cfg.load(repo_root / "mneme.yaml")
    rendered = rnd.render_all(entity)
    # five of the six components ship a template (gm_assistant has none)
    assert {d.component for d in rendered} == {
        "dgxlib",
        "turbovecdb",
        "mempalace",
        "rpg_lib",
        "CampaignGenerator",
    }
    for d in rendered:
        assert yaml.safe_load(d.content) is not None
