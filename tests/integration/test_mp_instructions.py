"""US5 instructions test (T044): the MCP server serves the method + per-campaign usage
guide on demand, with zero pasted docs (SC-013); usage guide is read from the campaign."""

from __future__ import annotations

from mneme.mcp import server
from tests.fixtures import entity_for, make_campaigns


def test_management_instructions_are_served_from_mneme():
    text = server.management_instructions()
    assert "Managing a Campaign Mempalace" in text
    assert "verbatim" in text.lower()  # the hard rules are present


def test_target_config_is_retrievable_without_hand_assembly(tmp_path):
    root = make_campaigns(tmp_path / "campaigns")
    tc = server.target_config(entity_for(root), "full")
    assert tc["campaign"] == "full"
    assert tc["recipe_version"] == "1.0.0"
    assert {w["name"] for w in tc["recommended"]["wings"]} == {"narrative", "chronicle", "full"}


def test_usage_guide_is_read_from_the_campaign_not_mneme(tmp_path):
    root = make_campaigns(tmp_path / "campaigns")
    guide = server.campaign_usage_guide(entity_for(root), "full")
    assert "Search the chronicle wing" in guide  # exactly what the campaign's MEMPALACE.md says
    # a campaign without a guide returns a clear placeholder, not an error
    assert "no MEMPALACE.md" in server.campaign_usage_guide(entity_for(root), "bare1")


def test_inventory_flags_oversized_bible(tmp_path):
    root = make_campaigns(tmp_path / "campaigns")
    big = root / "full" / "campaign_state.md"
    big.write_text("# Big\n" + "\n".join(f"line {i}" for i in range(2500)))
    inv = server.inventory(entity_for(root), "full")
    assert inv["bible"]["oversized"] is True
    assert inv["has_authority"] is True
