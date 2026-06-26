"""Foundational unit tests (T012): authority + recipe validation, render golden-files."""

from __future__ import annotations

import pytest

from mneme.mempalace import authority, recipe, render
from tests.fixtures import make_campaigns


def _write_authority(campaign_dir, body):
    (campaign_dir / ".mneme").mkdir(parents=True, exist_ok=True)
    (campaign_dir / ".mneme" / "mempalace.yaml").write_text(body)


# ── recipe ────────────────────────────────────────────────────────────────────


def test_recipe_current_loads_v1():
    rec = recipe.current()
    assert rec.version == "1.0.0"
    assert "summaries/" in rec.mechanical.baseline_exclusions
    assert rec.mechanical.tunnel_rooms == ("npcs", "world")
    assert any(p.id == "three_wing" for p in rec.scaffold)


def test_recipe_load_by_major():
    assert recipe.load("1.2.3").version == "1.0.0"  # major 1 → v1 file
    with pytest.raises(recipe.RecipeError):
        recipe.load("9.0.0")


# ── authority validation ────────────────────────────────────────────────────


def test_authority_loads_valid_full(tmp_path):
    root = make_campaigns(tmp_path / "campaigns")
    cfg = authority.load(root / "full")
    assert cfg.campaign == "full"
    assert {w.name for w in cfg.wings} == {"narrative", "chronicle", "full"}
    assert cfg.disposition_for("scaffold.wing.chronicle.absent").kind == "deliberate"


def test_authority_rejects_bad_trust_and_missing_source(tmp_path):
    c = tmp_path / "c"
    (c / "docs").mkdir(parents=True)
    _write_authority(
        c,
        'campaign: c\nrecipe_version: "1.0.0"\n'
        "wings:\n  - {name: w1, source: docs, trust: bogus, rooms: []}\n"
        "  - {name: w2, source: nope, trust: reference, rooms: []}\n",
    )
    with pytest.raises(authority.AuthorityError) as ei:
        authority.load(c)
    problems = "\n".join(ei.value.problems)
    assert "trust 'bogus'" in problems
    assert "does not exist" in problems


def test_authority_rejects_wing_order_violation(tmp_path):
    c = tmp_path / "c"
    (c / "docs" / "chapters").mkdir(parents=True)
    _write_authority(
        c,
        'campaign: c\nrecipe_version: "1.0.0"\n'
        "wings:\n  - {name: root, source: '.', trust: reference, rooms: []}\n"
        "  - {name: nar, source: docs/chapters, trust: authoritative, rooms: []}\n",
    )
    with pytest.raises(authority.AuthorityError) as ei:
        authority.load(c)
    assert "sub-scopes must be listed before" in "\n".join(ei.value.problems)


def test_authority_rejects_deliberate_without_rationale_and_forbidden_field(tmp_path):
    c = tmp_path / "c"
    (c / "docs").mkdir(parents=True)
    _write_authority(
        c,
        'campaign: c\nrecipe_version: "1.0.0"\nindex: oops\n'
        "wings:\n  - {name: w, source: docs, trust: reference, rooms: []}\n"
        "dispositions:\n"
        "  - {divergence: scaffold.nomatch, kind: deliberate, recorded: '2026-06-25'}\n",
    )
    with pytest.raises(authority.AuthorityError) as ei:
        authority.load(c)
    problems = "\n".join(ei.value.problems)
    assert "requires a rationale" in problems
    assert "forbidden field 'index'" in problems


# ── render golden-file + coherence ──────────────────────────────────────────


def test_render_produces_stamped_wings_and_ignore(tmp_path):
    root = make_campaigns(tmp_path / "campaigns")
    cfg = authority.load(root / "full")
    rec = recipe.load(cfg.recipe_version)
    arts = {str(a.target): a for a in render.render(cfg, rec)}

    assert "docs/chapters/mempalace.yaml" in arts
    assert "mempalace.yaml" in arts  # root wing (source ".")
    assert ".mempalaceignore" in arts

    ignore = arts[".mempalaceignore"].content
    assert "summaries/" in ignore  # recipe baseline
    assert "scratch/" in ignore  # extra_exclusions
    assert "docs/chapters/" in ignore  # double-mine guard for non-root wing
    assert "docs/distill_extractions/" in ignore

    wing = arts["docs/chapters/mempalace.yaml"].content
    assert "wing: narrative" in wing


def test_render_coherence_detects_tampering(tmp_path):
    root = make_campaigns(tmp_path / "campaigns")
    full = root / "full"
    cfg = authority.load(full)
    rec = recipe.load(cfg.recipe_version)
    # make_campaigns rendered full already → coherent
    assert render.coherent(cfg, rec, full) == []
    # hand-edit a derived file → detected as drifted
    (full / "docs" / "chapters" / "mempalace.yaml").write_text("wing: hacked\nrooms: []\n")
    drifted = render.coherent(cfg, rec, full)
    assert any(str(d) == "docs/chapters/mempalace.yaml" for d in drifted)
