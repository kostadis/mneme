"""Foundational unit tests (T012): authority + recipe validation, render golden-files."""

from __future__ import annotations

import pytest

from mneme.mempalace import authority, recipe, render
from tests.fixtures import make_campaigns


def _write_authority(campaign_dir, body):
    (campaign_dir / ".mneme").mkdir(parents=True, exist_ok=True)
    (campaign_dir / ".mneme" / "mempalace.yaml").write_text(body)


# ── recipe ────────────────────────────────────────────────────────────────────


def test_recipe_v2_standard():
    rec = recipe.load("2.0.0")
    assert rec.version == "2.0.0"  # v2 is the 6-wing standard (GH #24); current() is v3 (007)
    # notes/ and summaries/ are WINGS in v2, no longer baseline exclusions
    assert "summaries/" not in rec.mechanical.baseline_exclusions
    assert "notes/" not in rec.mechanical.baseline_exclusions
    assert rec.mechanical.tunnel_rooms == ("npcs", "world")
    assert rec.scaffold[0].id == "standard"  # the 6-wing model is preferred
    assert any(p.id == "three_wing" for p in rec.scaffold)  # fallbacks kept


def test_recipe_load_by_major():
    assert recipe.load("1.2.3").version == "1.0.0"  # major 1 → v1 file (preserved)
    assert recipe.load("2.1.0").version == "2.0.0"  # major 2 → v2 file
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
    assert "logs/" in ignore  # recipe baseline (v2; summaries/ is a wing now, not excluded)
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


# ── dual authority (007 T016, R8, FR-001a) ───────────────────────────────────

_NO_WINGS = 'campaign: c\nrecipe_version: "4.0.0"\nstore:\n  alias: c\n'


def _corpus(campaign_dir):
    (campaign_dir / ".mneme").mkdir(parents=True, exist_ok=True)
    (campaign_dir / ".mneme" / "corpus.yaml").write_text(
        "campaign: c\nkinds:\n  npcs:\n    dirs: [docs]\n"
    )


def test_corpus_campaign_allows_authority_without_wings(tmp_path):
    _corpus(tmp_path)
    _write_authority(tmp_path, _NO_WINGS)
    cfg = authority.load(tmp_path)
    assert cfg.wings == () and cfg.store.alias == "c"


def test_no_corpus_still_requires_wings(tmp_path):
    _write_authority(tmp_path, _NO_WINGS)
    with pytest.raises(authority.AuthorityError, match="at least one wing"):
        authority.load(tmp_path)


@pytest.mark.parametrize(
    "extra, key",
    [
        ("wings:\n  - name: w\n    source: .\n    trust: reference\n", "wings"),
        ("extra_exclusions:\n  - scratch/\n", "extra_exclusions"),
    ],
)
def test_corpus_plus_wing_keys_is_dual_authority(tmp_path, extra, key):
    _corpus(tmp_path)
    _write_authority(tmp_path, _NO_WINGS + extra)
    with pytest.raises(authority.AuthorityError) as ei:
        authority.load(tmp_path)
    (msg,) = ei.value.problems
    assert msg.startswith("dual-authority") and f"`{key}:`" in msg
    assert "mempalace.yaml" in msg and "corpus.yaml" in msg


def test_both_wing_keys_report_both(tmp_path):
    _corpus(tmp_path)
    _write_authority(
        tmp_path,
        _NO_WINGS + "wings:\n  - name: w\n    source: .\n    trust: reference\n"
        "extra_exclusions: [x/]\n",
    )
    with pytest.raises(authority.AuthorityError) as ei:
        authority.load(tmp_path)
    assert len(ei.value.problems) == 2
