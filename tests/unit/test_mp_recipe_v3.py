"""Recipe v3 `kinds:` (feature 007, R6)."""

from __future__ import annotations

from mneme.mempalace import recipe
from mneme.mempalace.models import TRUST_LEVELS


def test_current_is_v3():
    assert recipe.current().version == "3.0.0"


def test_v3_loads_five_kinds_with_ratified_trusts():
    rec = recipe.load("3.0.0")
    trusts = {k.name: k.default_trust for k in rec.kinds}
    assert trusts == {
        "npcs": "authoritative",
        "summaries": "authoritative",
        "party": "authoritative",
        "grounding": "authoritative",
        "prep": "reference",
    }
    assert all(t in TRUST_LEVELS for t in trusts.values())
    assert all(k.rooms_hint for k in rec.kinds)


def test_v3_keeps_v2_mechanical_and_scaffold():
    v2, v3 = recipe.load("2.0.0"), recipe.load("3.0.0")
    assert v3.mechanical == v2.mechanical
    assert v3.scaffold == v2.scaffold


def test_v1_and_v2_have_no_kinds():
    assert recipe.load("1.0.0").kinds == ()
    assert recipe.load("2.0.0").kinds == ()
