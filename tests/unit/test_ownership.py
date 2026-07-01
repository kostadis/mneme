"""005 — ownership classification, claim, and the host-independent invariant (US4, US5)."""

from __future__ import annotations

import pytest
import yaml

from hypostasis.models import MnemeIdentity
from mneme.mempalace import ownership
from mneme.mempalace.ownership import OwnerState, OwnershipError

ID_A = MnemeIdentity(id="11111111-1111-1111-1111-111111111111", label="fleet-a")
ID_B = MnemeIdentity(id="22222222-2222-2222-2222-222222222222", label="fleet-b")


def _camp(tmp_path):
    c = tmp_path / "toee"
    c.mkdir()
    return c


def test_classify_unintegrated(tmp_path):
    assert ownership.classify(_camp(tmp_path), ID_A) is OwnerState.UNINTEGRATED


def test_classify_owned_and_foreign(tmp_path):
    c = _camp(tmp_path)
    ownership.write_owner(c, ID_A)
    assert ownership.classify(c, ID_A) is OwnerState.OWNED
    assert ownership.classify(c, ID_B) is OwnerState.FOREIGN


def test_classify_unverifiable_without_identity(tmp_path):
    c = _camp(tmp_path)
    ownership.write_owner(c, ID_A)
    assert ownership.classify(c, None) is OwnerState.UNVERIFIABLE


def test_write_owner_creates_only_owner_yaml(tmp_path):
    # SC-007 — claim writes exactly .mneme/owner.yaml, nothing else.
    c = _camp(tmp_path)
    ownership.write_owner(c, ID_A)
    assert list((c / ".mneme").iterdir()) == [c / ".mneme" / "owner.yaml"]


def test_owner_yaml_has_no_host_coordinate(tmp_path):
    # US5 / SC-009 — the record is host-independent.
    c = _camp(tmp_path)
    ownership.write_owner(c, ID_A)
    raw = yaml.safe_load((c / ".mneme" / "owner.yaml").read_text())
    blob = str(raw).lower()
    for forbidden in ("host", "machine", "hostname", "/", "127.0.0.1", "port"):
        assert forbidden not in str(raw.get("mneme", {})).lower(), raw
    assert raw["mneme"]["id"] == ID_A.id
    assert "schema_version" in raw and blob  # well-formed


def test_integrate_campaign_claims_then_idempotent(tmp_path):
    c = _camp(tmp_path)
    owner1 = ownership.integrate_campaign(c, ID_A)
    assert owner1.mneme_id == ID_A.id
    # idempotent — second integrate by the same mneme does not change ownership
    owner2 = ownership.integrate_campaign(c, ID_A)
    assert owner2.mneme_id == ID_A.id


def test_integrate_campaign_refuses_foreign(tmp_path):
    # FR-015 — a foreign-owned campaign is never re-stamped.
    c = _camp(tmp_path)
    ownership.write_owner(c, ID_A)
    with pytest.raises(OwnershipError):
        ownership.integrate_campaign(c, ID_B)
    # owner.yaml unchanged
    assert ownership.read_owner(c).mneme_id == ID_A.id


def test_brick_test_same_id_readopts_different_id_foreign(tmp_path):
    # US5 / SC-008 — ownership reconstructs from owner.yaml alone, by id match.
    c = _camp(tmp_path)
    ownership.write_owner(c, ID_A)
    same_id = MnemeIdentity(id=ID_A.id, label="a-different-label-same-id")
    assert ownership.classify(c, same_id) is OwnerState.OWNED  # label ignored, id matches
    assert ownership.classify(c, ID_B) is OwnerState.FOREIGN
