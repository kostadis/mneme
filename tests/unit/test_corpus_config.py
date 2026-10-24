"""`.mneme/corpus.yaml` loading + structural validation (feature 007, T013)."""

from __future__ import annotations

import hashlib

import pytest

from mneme.corpus import config
from mneme.mempalace import recipe

REC = recipe.current()


def _write(tmp_path, body, authority_campaign=None):
    (tmp_path / ".mneme").mkdir(exist_ok=True)
    (tmp_path / ".mneme" / "corpus.yaml").write_text(body)
    if authority_campaign:
        (tmp_path / ".mneme" / "mempalace.yaml").write_text(f"campaign: {authority_campaign}\n")
    return tmp_path


def _codes(tmp_path, body, **kw):
    _write(tmp_path, body, **kw)
    with pytest.raises(config.CorpusConfigError) as ei:
        config.load(tmp_path, REC)
    return [f.code for f in ei.value.findings], ei.value


GOOD = """\
campaign: toee
kinds:
  npcs:
    dirs: [docs/npcs]
  grounding:
    files: [docs/party.md, docs/world_state.md]
  prep:
    dirs: [notes/sessions]
    trust: accelerator
campaign_kinds:
  backstories:
    files: [docs/daz.md]
    trust: reference
"""


def test_valid_config_loads_with_effective_trust(tmp_path):
    _write(tmp_path, GOOD, authority_campaign="toee")
    cfg = config.load(tmp_path, REC)
    assert cfg.campaign == "toee"
    assert cfg.kinds["npcs"].trust == "authoritative"  # recipe default
    assert cfg.kinds["prep"].trust == "accelerator"  # override
    assert cfg.kinds["npcs"].standard and not cfg.kinds["backstories"].standard
    assert cfg.kinds["grounding"].files == ("docs/party.md", "docs/world_state.md")


def test_corpus_sha256_is_of_raw_bytes(tmp_path):
    _write(tmp_path, GOOD)
    cfg = config.load(tmp_path, REC)
    assert cfg.corpus_sha256 == hashlib.sha256(GOOD.encode()).hexdigest()


def test_has_corpus(tmp_path):
    assert not config.has_corpus(tmp_path)
    _write(tmp_path, GOOD)
    assert config.has_corpus(tmp_path)


def test_no_authority_means_no_campaign_check(tmp_path):
    _write(tmp_path, GOOD)  # out-of-the-abyss has no authority
    assert config.load(tmp_path, REC).campaign == "toee"


CASES = {
    "unknown-kind": "campaign: c\nkinds:\n  sumaries:\n    dirs: [a]\n",
    "shadowed-kind": "campaign: c\ncampaign_kinds:\n  npcs:\n    dirs: [a]\n    trust: reference\n",
    "missing-trust": "campaign: c\ncampaign_kinds:\n  lore:\n    dirs: [a]\n",
    "empty-declaration": "campaign: c\nkinds:\n  npcs: {}\n",
    "path-escape": "campaign: c\nkinds:\n  npcs:\n    files: [../x.md]\n",
    "unknown-key": "campaign: c\nkinds:\n  npcs:\n    dirs: [a]\n    mined_ass: true\n",
    "unknown-key ": "campaign: c\nextra: 1\nkinds:\n  npcs:\n    dirs: [a]\n",
    "invalid-trust": "campaign: c\nkinds:\n  npcs:\n    dirs: [a]\n    trust: gospel\n",
    "malformed": "kinds:\n  npcs:\n    dirs: [a]\n",  # no campaign
    "ambiguous-mining-kind": (
        "campaign: c\nkinds:\n  party:\n    files: [docs/party.md]\n"
        "  grounding:\n    files: [docs/party.md]\n"
    ),
    "trust-conflict": (
        "campaign: c\nkinds:\n  party:\n    files: [docs/party.md]\n    mined_as: true\n"
        "  prep:\n    files: [docs/party.md]\n"
    ),
}


@pytest.mark.parametrize("code", sorted(CASES))
def test_each_code_is_reported(tmp_path, code):
    codes, _ = _codes(tmp_path, CASES[code])
    assert code.strip() in codes


def test_campaign_mismatch(tmp_path):
    codes, err = _codes(tmp_path, GOOD, authority_campaign="obelisk")
    assert codes == ["campaign-mismatch"]
    assert "obelisk" in str(err) and "toee" in str(err)


@pytest.mark.parametrize("bad", ["/etc/passwd", "a/../../b", "..", ".", "a\\b"])
def test_path_escape_variants(tmp_path, bad):
    codes, _ = _codes(tmp_path, f"campaign: c\nkinds:\n  npcs:\n    dirs: ['{bad}']\n")
    assert "path-escape" in codes


def test_exactly_one_mined_as_resolves_a_shared_file(tmp_path):
    body = (
        "campaign: c\nkinds:\n  party:\n    files: [docs/party.md]\n    mined_as: true\n"
        "  grounding:\n    files: [docs/party.md]\n"
    )
    _write(tmp_path, body)
    assert set(config.load(tmp_path, REC).kinds) == {"party", "grounding"}


def test_file_inside_another_kinds_dir_is_shared(tmp_path):
    codes, _ = _codes(
        tmp_path,
        "campaign: c\nkinds:\n  npcs:\n    dirs: [docs]\n  party:\n    files: [docs/party.md]\n",
    )
    assert codes == ["ambiguous-mining-kind"]


def test_two_marks_is_ambiguous(tmp_path):
    codes, _ = _codes(
        tmp_path,
        "campaign: c\nkinds:\n  party:\n    files: [p.md]\n    mined_as: true\n"
        "  grounding:\n    files: [p.md]\n    mined_as: true\n",
    )
    assert codes == ["ambiguous-mining-kind"]


def test_all_findings_reported_at_once(tmp_path):
    codes, err = _codes(
        tmp_path,
        "campaign: c\nkinds:\n  sumaries:\n    dirs: [a]\n  npcs: {}\n",
    )
    assert set(codes) == {"unknown-kind", "empty-declaration"}
    assert err.findings[0].detail


def test_malformed_yaml_and_non_mapping(tmp_path):
    codes, _ = _codes(tmp_path, "campaign: [unclosed\n")
    assert codes == ["malformed"]
    codes, _ = _codes(tmp_path, "- a\n- b\n")
    assert codes == ["malformed"]


def test_recipe_without_kinds_makes_the_corpus_invalid(tmp_path):
    _write(tmp_path, GOOD)
    with pytest.raises(config.CorpusConfigError) as ei:
        config.load(tmp_path, recipe.load("2.0.0"))
    assert {f.code for f in ei.value.findings} == {"recipe-no-kinds"}
    assert "defines no kinds" in str(ei.value)
