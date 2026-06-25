"""T030 — apply: one-value change re-renders, leaves no stale copy (SC-004, Principle V)."""

from __future__ import annotations

from pathlib import Path

import yaml

from hypostasis import config as cfg
from hypostasis import render as rnd
from hypostasis import status as sts


def _write_config(path: Path, endpoint: str, target: Path) -> None:
    raw = {
        "venv": str(path.parent / "venv"),
        "machines": {"dgx": {"endpoint": endpoint, "default_model": "m"}},
        "data_roots": {"fivetools": str(path.parent / "data")},
        "services": {"dgx": {"url": endpoint, "managed": False}},
        "components": {
            "cg": {
                "source": {"path": str(path.parent / "src")},
                "pin": "abc1234",
                "config_template": "wiring.yaml.j2",
                "config_target": str(target),
            }
        },
        "order": {"install": ["cg"], "startup": ["dgx"]},
    }
    path.write_text(yaml.safe_dump(raw))


def test_apply_rerenders_with_no_stale_copy(tmp_path):
    tdir = tmp_path / "templates"
    tdir.mkdir()
    (tdir / "wiring.yaml.j2").write_text("endpoint: {{ machines.dgx.endpoint }}\n")
    target = tmp_path / "out" / "wiring.yaml"
    cfg_path = tmp_path / "hypostasis.yaml"

    # v1 — render the old value
    _write_config(cfg_path, "http://OLD:8001/v1", target)
    e1 = cfg.load(cfg_path)
    rnd.render_and_write_all(e1, tdir)
    assert "OLD" in target.read_text()
    assert sts.render_row(e1, e1.components["cg"]).ok  # in sync at v1

    # change ONE value, then apply (re-render)
    _write_config(cfg_path, "http://NEW:8001/v1", target)
    e2 = cfg.load(cfg_path)

    # before apply: status sees drift (stamp is v1, authority is v2)
    assert not sts.render_row(e2, e2.components["cg"]).ok

    written = rnd.render_and_write_all(e2, tdir)

    # after apply: new value present, OLD value GONE (no stale copy), stamp fresh
    assert target in written
    body = target.read_text()
    assert "NEW" in body
    assert "OLD" not in body
    assert sts.render_row(e2, e2.components["cg"]).ok


def test_apply_is_idempotent(tmp_path):
    tdir = tmp_path / "templates"
    tdir.mkdir()
    (tdir / "wiring.yaml.j2").write_text("endpoint: {{ machines.dgx.endpoint }}\n")
    target = tmp_path / "out" / "wiring.yaml"
    cfg_path = tmp_path / "hypostasis.yaml"
    _write_config(cfg_path, "http://x:8001/v1", target)
    entity = cfg.load(cfg_path)

    rnd.render_and_write_all(entity, tdir)
    first = target.read_text()
    rnd.render_and_write_all(entity, tdir)
    assert target.read_text() == first  # same authority → identical bytes (same stamp)
