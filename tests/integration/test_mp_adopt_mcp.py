"""FR-030: the confirm-gated MCP adopt tool — preview writes nothing; confirm writes
only mneme-managed files into the active checkout, leaving campaign content untouched."""

from __future__ import annotations

from mneme.mcp import server
from tests.fixtures import entity_for, make_campaigns


def _behind(root):
    """Put `full` one version behind so adopt has a real change to apply."""
    auth = root / "full" / ".mneme" / "mempalace.yaml"
    auth.write_text(auth.read_text().replace('recipe_version: "1.0.0"', 'recipe_version: "0.9.0"'))
    return auth


def test_preview_writes_nothing(tmp_path):
    root = make_campaigns(tmp_path / "campaigns")
    auth = _behind(root)
    before = auth.read_text()

    res = server.adopt(entity_for(root), "full", confirm=False)
    assert res["action"] == "preview"
    assert any("0.9.0" in c and "1.0.0" in c for c in res["diff"]["changed"])
    assert auth.read_text() == before  # nothing written on preview


def test_confirm_writes_only_mneme_files_into_active_checkout(tmp_path):
    root = make_campaigns(tmp_path / "campaigns")
    _behind(root)
    content = root / "full" / "campaign_state.md"
    content_before = content.read_text()

    res = server.adopt(entity_for(root), "full", confirm=True)
    assert res["action"] == "applied"
    assert ".mneme/mempalace.yaml" in res["written"]
    # the authority was upgraded in place
    auth_text = (root / "full" / ".mneme" / "mempalace.yaml").read_text()
    assert "recipe_version: 1.0.0" in auth_text or 'recipe_version: "1.0.0"' in auth_text
    # campaign CONTENT is untouched — only mneme-managed files were written (FR-030)
    assert content.read_text() == content_before


def test_adopt_without_authority_is_an_error_not_a_write(tmp_path):
    root = make_campaigns(tmp_path / "campaigns")
    res = server.adopt(entity_for(root), "bare1", confirm=True)
    assert "error" in res and "bootstrap" in res["error"]
    assert not (root / "bare1" / ".mneme").exists()
