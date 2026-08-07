"""005 — mneme identity minting in the config authority (US4, FR-012)."""

from __future__ import annotations

import pytest
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


# ── 006 — adopt / mint: the fleet identity becomes portable (US1) ────────────────


def _read(path) -> str:
    return open(path).read()


def test_adopt_writes_identity_when_absent(tmp_path):
    # FR-001 — a second host JOINS the fleet instead of minting its own id.
    path = _write_config(tmp_path)
    adopted = cfg.adopt_mneme_identity(path, "64cf8b36-e823-4b8e-8353-d08fe707f9be")
    assert adopted.id == "64cf8b36-e823-4b8e-8353-d08fe707f9be"
    assert cfg.load(path).mneme_identity.id == adopted.id


def test_adopt_preserves_operator_content(tmp_path):
    # research R1 — hypostasis.yaml is hand-authored and comment-dense; never a YAML rewrite.
    path = _write_config(tmp_path)
    before = _read(path)
    cfg.adopt_mneme_identity(path, "abc-123")
    after = _read(path)
    assert "# operator's hand-authored config" in after
    assert after.startswith(before.rstrip("\n"))


def test_adopt_replaces_only_the_mneme_block(tmp_path):
    # Replacing an existing identity must not disturb anything else in the file.
    path = _write_config(tmp_path, extra={"mneme": {"id": "old-id", "label": "old-label"}})
    open(path, "a").write("\n# a trailing operator comment\n")
    cfg.adopt_mneme_identity(path, "new-id", label="new-label")
    after = _read(path)
    ident = cfg.load(path).mneme_identity
    assert ident.id == "new-id" and ident.label == "new-label"
    assert "old-id" not in after and "old-label" not in after
    assert "# a trailing operator comment" in after
    assert "# operator's hand-authored config" in after


@pytest.mark.parametrize("bad", ["", "   ", "has space", "/home/kroussos/id", "a\nmneme:\n  id: x"])
def test_adopt_rejects_malformed_id_without_writing(tmp_path, bad):
    # Edge case — rejected BEFORE the config authority is touched.
    path = _write_config(tmp_path)
    before = _read(path)
    with pytest.raises(cfg.ConfigError):
        cfg.adopt_mneme_identity(path, bad)
    assert _read(path) == before


def test_mint_generates_a_new_id_and_is_not_adopt(tmp_path):
    # FR-003/006 — minting stays available, but it is now an explicit act.
    path = _write_config(tmp_path)
    minted = cfg.mint_mneme_identity(path, label="laptop-fleet")
    assert minted.id and minted.label == "laptop-fleet"
    assert cfg.load(path).mneme_identity.id == minted.id


def test_adopt_round_trips_through_load(tmp_path):
    # The written block must be valid YAML that the loader accepts (no hand-rolled corruption).
    path = _write_config(tmp_path)
    cfg.adopt_mneme_identity(path, "id-1", label="one")
    cfg.adopt_mneme_identity(path, "id-2")
    ident = cfg.load(path).mneme_identity
    assert ident.id == "id-2" and ident.label is None


# ── 006 — the adopt-or-mint decision table (US1, FR-002/003/004/005) ─────────────


def _tree_with_owners(tmp_path, **campaign_to_id):
    """Build a campaigns tree whose campaigns declare the given owner ids."""
    from hypostasis.models import MnemeIdentity
    from mneme.mempalace import ownership
    from tests.fixtures import make_simple_campaign

    tree = tmp_path / "trees"
    for name, owner_id in campaign_to_id.items():
        camp = make_simple_campaign(tree, name)
        if owner_id:
            ownership.write_owner(camp, MnemeIdentity(id=owner_id))
    return tree


def _entity_and_config(tmp_path, tree):
    from tests.fixtures import entity_for_trees

    return entity_for_trees(tree), _write_config(tmp_path)


def test_resolve_identity_mints_on_greenfield(tmp_path):
    # FR-003 — nothing to adopt, so the 005 first-run experience is unchanged.
    from mneme import cli

    tree = _tree_with_owners(tmp_path, fresh=None)
    entity, path = _entity_and_config(tmp_path, tree)
    identity = cli.resolve_identity(entity, path)
    assert identity.id
    assert cfg.load(path).mneme_identity.id == identity.id


def test_resolve_identity_refuses_when_one_fleet_is_present(tmp_path):
    # FR-002 — the Brick Test: adopt what the campaigns already declare, never re-mint.
    from mneme import cli

    tree = _tree_with_owners(tmp_path, toee="fleet-a", obelisk="fleet-a")
    entity, path = _entity_and_config(tmp_path, tree)
    before = _read(path)
    with pytest.raises(cli.IdentityUndecided) as ei:
        cli.resolve_identity(entity, path)
    msg = "\n".join(ei.value.lines)
    assert "fleet-a" in msg and "toee" in msg and "obelisk" in msg
    assert "mneme identity adopt fleet-a" in msg and "mneme identity mint" in msg
    assert _read(path) == before  # FR-005/008 — refusing wrote nothing


def test_resolve_identity_refuses_and_lists_when_several_fleets_present(tmp_path):
    # FR-004 — never guess between fleets.
    from mneme import cli

    tree = _tree_with_owners(tmp_path, toee="fleet-a", hillsfar="fleet-b")
    entity, path = _entity_and_config(tmp_path, tree)
    with pytest.raises(cli.IdentityUndecided) as ei:
        cli.resolve_identity(entity, path)
    msg = "\n".join(ei.value.lines)
    assert "fleet-a" in msg and "fleet-b" in msg
    assert "adopt <id>" in msg and "mneme identity mint" in msg


def test_resolve_identity_returns_established_identity_unchanged(tmp_path):
    from hypostasis.models import MnemeIdentity
    from mneme import cli
    from tests.fixtures import entity_for_trees

    tree = _tree_with_owners(tmp_path, toee="fleet-a")
    entity = entity_for_trees(tree, identity=MnemeIdentity(id="fleet-a"))
    assert cli.resolve_identity(entity, _write_config(tmp_path)).id == "fleet-a"
