"""mneme's advisory MCP server (US5, FR-022/028/029) — read-only.

The data tools and instruction payloads are pure functions (testable without the MCP
SDK or a running server); `build_server`/`run` wire them onto FastMCP lazily, so the
package imports even when `mcp` is not installed. No tool mutates anything — every
write stays in the `mneme mp` CLI behind preview-then-apply (Principle IV/VI).
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from hypostasis.models import ConfigEntity
from mneme.mempalace import authority as _authority
from mneme.mempalace import conform as _conform
from mneme.mempalace import discover as _discover
from mneme.mempalace import recipe as _recipe
from mneme.mempalace import target as _target

INSTRUCTIONS_DIR = Path(__file__).resolve().parent.parent / "recipes" / "instructions"


# ── pure data/instruction functions (the tool bodies) ────────────────────────


def target_config(entity: ConfigEntity, campaign: str) -> dict:
    """FR-022: what mneme recommends this campaign adopt (advisory)."""
    ref = _discover.find(entity, campaign)
    if not ref.has_authority:
        return {"campaign": campaign, "error": "no authority — bootstrap first"}
    cfg = _authority.load(ref.path)
    t = _target.resolve(cfg, _recipe.current())
    return {
        "campaign": t.campaign,
        "recipe_version": t.recipe_version,
        "recommended": {
            "wings": [
                {"name": w.name, "source": w.source, "trust": w.trust} for w in t.recommended.wings
            ],
            "extra_exclusions": list(t.recommended.extra_exclusions),
        },
        "diff": {
            "added": list(t.added),
            "changed": list(t.changed),
            "preserved": list(t.preserved),
            "conflicts": list(t.conflicts),
        },
    }


def status(entity: ConfigEntity, campaign: str | None = None) -> list[dict]:
    """FR-005/008/027: honest conformance rows (with dispositions)."""
    report = _conform.report(entity, campaign=campaign)
    out = []
    for r in report.rows:
        out.append(
            {
                "campaign": r.campaign,
                "dimension": r.dimension,
                "state": r.state.value,
                "ok": r.ok,
                "disposition": asdict(r.disposition) if r.disposition else None,
                "note": r.note,
            }
        )
    return out


def inventory(entity: ConfigEntity, campaign: str) -> dict:
    """Current document/wing structure, so an assistant can reason about a migration."""
    ref = _discover.find(entity, campaign)
    md_files = [p for p in ref.path.rglob("*.md") if ".mneme" not in p.parts]
    bible = max(md_files, key=lambda p: len(p.read_text().splitlines()), default=None)
    wings = []
    if ref.has_authority:
        cfg = _authority.load(ref.path)
        for w in cfg.wings:
            n = len(list((ref.path / w.source).glob("*.md")))
            wings.append({"name": w.name, "source": w.source, "files": n})
    bible_info = None
    if bible is not None:
        lines = len(bible.read_text().splitlines())
        bible_info = {
            "path": str(bible.relative_to(ref.path)),
            "lines": lines,
            "oversized": lines > 2000,
        }
    return {
        "campaign": campaign,
        "has_authority": ref.has_authority,
        "wings": wings,
        "doc_count": len(md_files),
        "bible": bible_info,
    }


def adopt(entity: ConfigEntity, campaign: str, confirm: bool = False) -> dict:
    """FR-030: the one write tool — confirm-gated, single-campaign adoption.

    `confirm=False` previews (writes nothing); `confirm=True` writes the upgraded
    authority + re-rendered files into the active checkout (mneme-managed files only,
    uncommitted). Two-step by construction: the assistant previews, the human approves.
    """
    from mneme.mempalace import publish as _publish
    from mneme.mempalace.workcopy import WorkingCopyError

    ref = _discover.find(entity, campaign)
    if not ref.has_authority:
        return {"campaign": campaign, "error": "no authority — bootstrap first"}
    cfg = _authority.load(ref.path)
    diff = _target.resolve(cfg, _recipe.current())
    preview = {
        "campaign": campaign,
        "recipe_version": diff.recipe_version,
        "diff": {"added": list(diff.added), "changed": list(diff.changed),
                 "preserved": list(diff.preserved), "conflicts": list(diff.conflicts)},
    }
    if not confirm:
        preview["action"] = "preview"
        preview["note"] = (
            "call adopt(campaign, confirm=true) to write these into your "
            "active checkout (uncommitted)"
        )
        return preview
    try:
        written, _ = _publish.adopt_in_place(entity, campaign)
    except WorkingCopyError as e:
        return {"campaign": campaign, "error": str(e)}
    preview["action"] = "applied"
    preview["written"] = [str(p.relative_to(ref.path)) for p in written]
    preview["note"] = (
        "adopted into your active checkout (mneme-managed files only) — review and commit"
    )
    return preview


def management_instructions() -> str:
    """FR-028/029: the mneme-owned method, served on demand."""
    return (INSTRUCTIONS_DIR / "manage-mempalace.md").read_text()


def campaign_usage_guide(entity: ConfigEntity, campaign: str) -> str:
    """FR-028/029: the campaign's own MEMPALACE.md usage guide (served from the campaign)."""
    ref = _discover.find(entity, campaign)
    guide = ref.path / "MEMPALACE.md"
    if not guide.is_file():
        return f"(no MEMPALACE.md usage guide for {campaign})"
    return guide.read_text()


# ── FastMCP wiring (lazy import so the package loads without `mcp`) ────────────


def build_server(entity: ConfigEntity):
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as e:  # pragma: no cover - exercised only when mcp absent
        raise RuntimeError(
            "the MCP server needs the optional 'mcp' dependency — install: pip install '.[mcp]'"
        ) from e

    mcp = FastMCP("mneme")

    @mcp.tool()
    def get_target_config(campaign: str) -> dict:
        """What mneme recommends this campaign adopt (advisory; reading changes nothing)."""
        return target_config(entity, campaign)

    @mcp.tool()
    def get_status(campaign: str | None = None) -> list[dict]:
        """Observed per-campaign conformance, each divergence paired with its disposition."""
        return status(entity, campaign)

    @mcp.tool()
    def get_campaign_inventory(campaign: str) -> dict:
        """The campaign's current document/wing structure (migration-planning input)."""
        return inventory(entity, campaign)

    @mcp.tool()
    def adopt_campaign(campaign: str, confirm: bool = False) -> dict:
        """Adopt the current recipe for ONE campaign (FR-030). confirm=False previews;
        confirm=True writes the upgraded mneme-managed files into the active checkout,
        uncommitted, for human review. Call once to preview, again with confirm=true."""
        return adopt(entity, campaign, confirm)

    @mcp.resource("mneme://instructions/manage-mempalace")
    def manage_mempalace() -> str:
        """The mneme-owned method for building/migrating a mempalace."""
        return management_instructions()

    @mcp.resource("mneme://campaign/{campaign}/usage-guide")
    def usage_guide(campaign: str) -> str:
        """A specific campaign's usage guide (served from its MEMPALACE.md)."""
        return campaign_usage_guide(entity, campaign)

    return mcp


def run(entity: ConfigEntity) -> None:  # pragma: no cover - process entry
    build_server(entity).run()
