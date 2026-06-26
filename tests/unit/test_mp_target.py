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
