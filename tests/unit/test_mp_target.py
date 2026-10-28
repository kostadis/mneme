"""US3 unit test (T024): target resolution preserves choices; surfaces conflicts."""

from __future__ import annotations

from mneme.mempalace import authority, recipe, target
from tests.fixtures import make_campaigns


def test_resolve_preserves_choices_and_bumps_version(tmp_path):
    root = make_campaigns(tmp_path / "campaigns")
    cfg = authority.load(root / "full")
    # pretend the campaign is one minor behind
    cfg = cfg.__class__(**{**cfg.__dict__, "recipe_version": "0.9.0"})
    rec = recipe.current()
    t = target.resolve(cfg, rec)
    assert t.recipe_version == rec.version
    assert "narrative" in t.preserved and "chronicle" in t.preserved
    assert any("0.9.0" in c and rec.version in c for c in t.changed)
    assert t.recommended.wings == cfg.wings  # content choices untouched


def test_resolve_surfaces_deliberate_mechanical_conflict(tmp_path):
    root = make_campaigns(tmp_path / "campaigns")
    c = root / "full"
    auth = c / ".mneme" / "mempalace.yaml"
    auth.write_text(
        auth.read_text()
        + "  - {divergence: mechanical.exclusions.notes/, kind: deliberate, "
        "rationale: 'we index notes on purpose', recorded: '2026-06-25'}\n"
    )
    cfg = authority.load(c)
    t = target.resolve(cfg, recipe.current())
    assert "mechanical.exclusions.notes/" in t.conflicts


def test_resolve_adds_only_the_recipe_delta(tmp_path):
    """#79: an upgrade reports only baseline exclusions the new recipe adds over the
    campaign's current recipe, not the whole baseline."""
    root = make_campaigns(tmp_path / "campaigns")
    cfg = authority.load(root / "full")
    rec = recipe.current()
    cfg = cfg.__class__(**{**cfg.__dict__, "recipe_version": rec.version})
    assert target.resolve(cfg, rec).added == ()


def test_resolve_corpus_campaign_adds_no_baseline_exclusions(tmp_path):
    """#79: a corpus campaign renders no ignore file, so the preview reports no
    baseline exclusions even from a recipe that is not installed."""
    root = make_campaigns(tmp_path / "campaigns")
    cfg = authority.load(root / "full")
    cfg = cfg.__class__(**{**cfg.__dict__, "recipe_version": "0.9.0", "extra_exclusions": ()})
    rec = recipe.current()
    wing = target.resolve(cfg, rec)
    assert wing.added == ()  # unknown prior: flagged, not over-reported
    assert any("0.9.0 not installed" in c for c in wing.changed)
    corpus = target.resolve(cfg, rec, corpus=True)
    assert corpus.added == () and not any("baseline" in c for c in corpus.changed)


def test_resolve_reports_cross_version_adds_and_drops(tmp_path):
    """#79: a v1 wing campaign moving to the current recipe sees exactly the delta."""
    root = make_campaigns(tmp_path / "campaigns")
    cfg = authority.load(root / "full")
    cfg = cfg.__class__(**{**cfg.__dict__, "recipe_version": "1.0.0", "extra_exclusions": ()})
    v1, rec = recipe.load("1.0.0"), recipe.current()
    old, new = v1.mechanical.baseline_exclusions, rec.mechanical.baseline_exclusions
    t = target.resolve(cfg, rec)
    assert t.added == tuple(x for x in new if x not in old)
    dropped = [x for x in old if x not in new]
    assert dropped and any(all(d in c for d in dropped) for c in t.changed)
