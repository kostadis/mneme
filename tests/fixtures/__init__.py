"""Shared test fixtures for `mneme mp`.

`make_campaigns(root)` builds a campaigns tree mirroring the real spread:
- `full`        — 3 wings + `.mempalaceignore` + a per-campaign `MEMPALACE.md` usage
                  guide (the *excluded* file, distinct from the repo-level
                  `MEMPALACE_HOWTO.md` recipe) + a `.mneme/mempalace.yaml` authority.
- `ignore-only` — only a `.mempalaceignore`, no authority (like Phandalin).
- `bare1/2/3`   — nothing (like Hillsfar/Obelisk/toee).

`stub_mempalace_path()` returns the path to the recording stub binary.
"""

from __future__ import annotations

from pathlib import Path

from hypostasis.models import ConfigEntity, Machine, Order

STUB = Path(__file__).parent / "stub_mempalace.py"


def entity_for(campaigns_root: Path) -> ConfigEntity:
    """A minimal ConfigEntity pointing data_roots.campaigns at ``campaigns_root``.

    Built directly (no validation) — these tests exercise the mp manager, not the
    hypostasis.yaml loader. venv is left unset so the runner falls back to PATH /
    an injected runner.
    """
    return ConfigEntity(
        venv=Path("."),
        machines={"dgx": Machine("http://dgx:8001/v1")},
        services={},
        components={},
        order=Order(install=(), startup=()),
        data_roots={"campaigns": campaigns_root},
    )

FULL_AUTHORITY = """\
campaign: full
recipe_version: "2.0.0"
wings:
  - name: narrative
    source: docs/chapters
    trust: authoritative
    rooms:
      - name: chapters
        description: Narrative prose chapters
        keywords: [chapter, session]
      - name: general
        description: Fallback
        keywords: []
  - name: chronicle
    source: docs/distill_extractions
    trust: accelerator
    rooms:
      - name: npcs
        description: NPC snapshots across the timeline
        keywords: [npc, character]
      - name: world
        description: World events and factions
        keywords: [world, faction]
  - name: full
    source: .
    trust: reference
    rooms:
      - name: npcs
        description: NPC dossiers
        keywords: [npc, dossier]
      - name: general
        description: Top-level docs
        keywords: []
extra_exclusions:
  - scratch/
dispositions:
  - divergence: scaffold.wing.chronicle.absent
    kind: deliberate
    rationale: "Has an extraction pipeline; chronicle wing intentional."
    recorded: "2026-06-25"
"""


def _render_full(full: Path) -> None:
    from mneme.mempalace import authority, recipe, render

    cfg = authority.load(full)
    render.write_all(cfg, recipe.load(cfg.recipe_version), full)


def make_greenfield_campaign(root: Path, name: str = "stormhaven") -> Path:
    """A NEW campaign (documents, NO `.mneme/` setup) — the input to bring-up (003).

    Returns the campaign dir. Has a docs/chapters wing-able dir + a root-level doc, so
    the scaffold picks a real pattern and there is something to index.
    """
    camp = root / name
    (camp / "docs" / "chapters").mkdir(parents=True)
    (camp / "docs" / "chapters" / "chapter_01.md").write_text("# Chapter 1\nThe vault opens.\n")
    (camp / "world.md").write_text("# World\nStormhaven stands.\n")
    return camp


def make_campaigns(root: Path) -> Path:
    """Create the fixture campaigns under ``root`` and return ``root``."""
    root.mkdir(parents=True, exist_ok=True)

    full = root / "full"
    (full / "docs" / "chapters").mkdir(parents=True)
    (full / "docs" / "distill_extractions").mkdir(parents=True)
    (full / ".mneme").mkdir()
    (full / "docs" / "chapters" / "chapter_01.md").write_text("# Chapter 1\nArrival.\n")
    (full / "docs" / "distill_extractions" / "extract_001.md").write_text("## NPCs\nDaz.\n")
    (full / "campaign_state.md").write_text("# State\nWhat is true now.\n")
    (full / "MEMPALACE.md").write_text("# Usage\nSearch the chronicle wing for NPCs.\n")
    (full / ".mneme" / "mempalace.yaml").write_text(FULL_AUTHORITY)
    # Render the derived wing yamls + .mempalaceignore (stamped) — `full` is an
    # already-adopted campaign, so its derived files are coherent with its authority.
    _render_full(full)

    ignore_only = root / "ignore-only"
    ignore_only.mkdir()
    (ignore_only / ".mempalaceignore").write_text("summaries/\n")
    (ignore_only / "world.md").write_text("# World\n")

    for name in ("bare1", "bare2", "bare3"):
        bare = root / name
        bare.mkdir()
        (bare / "notes.md").write_text("# Notes\n")

    return root
