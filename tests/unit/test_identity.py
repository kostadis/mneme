"""005 — mneme identity minting in the config authority (US4, FR-012)."""

from __future__ import annotations

import yaml

from hypostasis import config as cfg


def _write_config(tmp_path, extra: dict | None = None) -> str:
    raw = {
        "venv": str(tmp_path / "venv"),
        "machines": {"dgx": {"endpoint": "http://dgx:8001/v1"}},
        "data_roots": {"campaigns": [str(tmp_path / "t1")]},
        "services": {"dgx": {"url": "http://dgx:8001/v1", "managed": False}},
        "components": {"comp": {"source": {"path": str(tmp_path / "src")}, "pin": "abc1234"}},
        "order": {"install": ["comp"], "startup": ["dgx"]},
    }
    if extra:
        raw.update(extra)
    p = tmp_path / "hypostasis.yaml"
    p.write_text("# operator's hand-authored config\n" + yaml.safe_dump(raw))
    return str(p)


def test_mint_generates_and_persists(tmp_path):
    path = _write_config(tmp_path)
    assert cfg.load(path).mneme_identity is None
    identity = cfg.ensure_mneme_identity(path)
    assert identity.id
    # persisted and reloadable
    assert cfg.load(path).mneme_identity.id == identity.id


def test_mint_is_idempotent(tmp_path):
    path = _write_config(tmp_path)
    first = cfg.ensure_mneme_identity(path)
    second = cfg.ensure_mneme_identity(path)
    assert first.id == second.id


def test_mint_preserves_existing_content(tmp_path):
    # The targeted append must not clobber the operator's file (R3).
    path = _write_config(tmp_path)
    before = open(path).read()
    cfg.ensure_mneme_identity(path)
    after = open(path).read()
    assert after.startswith(before.rstrip("\n"))  # original content intact, block appended
    assert "# operator's hand-authored config" in after
    assert "mneme:" in after


def test_existing_identity_returned_unchanged(tmp_path):
    path = _write_config(tmp_path, extra={"mneme": {"id": "fixed-id-123", "label": "main"}})
    identity = cfg.ensure_mneme_identity(path)
    assert identity.id == "fixed-id-123" and identity.label == "main"


def test_mneme_block_without_id_is_rejected(tmp_path):
    path = _write_config(tmp_path, extra={"mneme": {"label": "no-id"}})
    import pytest

    with pytest.raises(cfg.ConfigError):
        cfg.load(path)
