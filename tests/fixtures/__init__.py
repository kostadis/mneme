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

from hypostasis.models import ConfigEntity, Machine, MnemeIdentity, Order

STUB = Path(__file__).parent / "stub_mempalace.py"


def _fake_owner(base: Path) -> tuple[Path, Path]:
    """A hermetic owning-mneme stand-in under ``base`` (outside any campaign tree): a fake venv
    with `bin/mneme` + `bin/mempalace-mcp`, and a hypostasis.yaml. Returns (venv, yaml)."""
    venv = base / ".fake-venv"
    for prog in ("mneme", "mempalace-mcp"):
        exe = venv / "bin" / prog
        exe.parent.mkdir(parents=True, exist_ok=True)
        exe.touch(exist_ok=True)
        exe.chmod(0o755)
    cfg = base / "hypostasis.yaml"
    if not cfg.exists():
        cfg.write_text("# fake hypostasis config for tests\n")
    return venv, cfg


def fake_binding(base: Path, env: dict | None = None):
    """An McpBinding onto the hermetic fake owner under ``base`` (see `_fake_owner`)."""
    from mneme.mempalace.mcpface import McpBinding, declared_mcp_env

    venv, cfg = _fake_owner(base)
    return McpBinding(
        mneme_program=venv / "bin" / "mneme",
        mempalace_program=venv / "bin" / "mempalace-mcp",
        config_path=cfg,
        env=declared_mcp_env(env),
    )


def entity_for(campaigns_root: Path, *, mempalace: Path | None = None) -> ConfigEntity:
    """A minimal ConfigEntity pointing data_roots.campaigns at ``campaigns_root``.

    Built directly (no validation) — these tests exercise the mp manager, not the
    hypostasis.yaml loader. venv is a hermetic fake venv (with `mneme` and `mempalace-mcp`
    programs) and source_path a fake hypostasis.yaml, both beside ``campaigns_root`` — the
    owning-mneme binding for the .mcp.json face needs them. ``mempalace`` declares this "host's"
    palace root (006).
    """
    roots: dict = {"campaigns": campaigns_root}
    if mempalace is not None:
        roots["mempalace"] = mempalace  # normalized to a 1-tuple by ConfigEntity
    venv, cfg = _fake_owner(Path(campaigns_root).parent)
    return ConfigEntity(
        venv=venv,
        source_path=cfg,
        machines={"dgx": Machine("http://dgx:8001/v1")},
        services={},
        components={},
        order=Order(install=(), startup=()),
        data_roots=roots,
    )


def entity_for_trees(
    *campaign_trees: Path,
    identity: MnemeIdentity | None = None,
    mempalace: Path | None = None,
) -> ConfigEntity:
    """A ConfigEntity declaring one-or-more campaign trees (005), optionally with a
    minted mneme identity and this host's palace root (006). The fake owning venv/config live
    in the first tree's parent (outside every tree)."""
    roots: dict = {"campaigns": [str(t) for t in campaign_trees]}
    if mempalace is not None:
        roots["mempalace"] = mempalace  # normalized to a 1-tuple by ConfigEntity
    venv, cfg = _fake_owner(Path(campaign_trees[0]).parent)
    return ConfigEntity(
        venv=venv,
        source_path=cfg,
        machines={"dgx": Machine("http://dgx:8001/v1")},
        services={},
        components={},
        order=Order(install=(), startup=()),
        data_roots=roots,
        mneme_identity=identity,
    )


def make_simple_campaign(tree: Path, name: str) -> Path:
    """Create ``tree/name`` as a minimal campaign dir (a single doc) and return it."""
    camp = tree / name
    camp.mkdir(parents=True, exist_ok=True)
    (camp / "world.md").write_text(f"# {name}\n")
    return camp

FULL_AUTHORITY = """\
campaign: full
recipe_version: "4.0.0"
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


def add_store_pointer(root: Path, name: str = "full") -> None:
    """Give an authority-bearing fixture campaign a `store:` pointer (refresh is fail-closed
    without one — GH #26: it cannot verify a palace it cannot name)."""
    p = root / name / ".mneme" / "mempalace.yaml"
    p.write_text(p.read_text() + f"store:\n  alias: {name}\n")


ONNX_ENV = {"MEMPALACE_EMBEDDING_PROVIDER": "onnx"}  # explicit embedder (GH #26: no guessing)


def with_onnx(entity):
    """``entity`` declaring the onnx embedder (dim 384, what the stub store records)."""
    import dataclasses

    return dataclasses.replace(entity, env={**entity.env, **ONNX_ENV})
