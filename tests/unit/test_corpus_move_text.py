"""#71: the adopt-time move of a campaign kind to `kinds:` is a targeted text edit, atomic,
disclosed in every preview, and refuses what it cannot edit safely."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import yaml
from typer.testing import CliRunner

from mneme.corpus import config as cconfig
from mneme.mcp import server
from mneme.mempalace import cli as mpcli
from mneme.mempalace import publish
from mneme.mempalace import recipe as recipe_mod
from mneme.mempalace.corpus_guard import CorpusRefusal, MoveRefused, move_shadowed_text
from tests.fixtures.corpus_campaign import corpus_world, tree_snapshot

CLI = CliRunner()

COMMENTED = """\
# the Toee corpus
campaign: corp

kinds:
  npcs:
    dirs: [docs/npcs]   # flow list stays
  summaries:
    dirs: [docs/summaries]

# our own kinds
campaign_kinds:
  lore:
    dirs: [docs/lore]
    trust: reference
  arcs:   # the arcs
    # why: tracked by hand
    dirs: [docs/arcs]
    files: ["docs/arcs/a.md"]
    trust: authoritative
"""


@pytest.fixture
def w(tmp_path, monkeypatch):
    world = corpus_world(tmp_path, monkeypatch)
    monkeypatch.setattr(mpcli, "_load_or_exit", lambda _c: world.entity)
    return world


def _v3(w, text):
    auth = w.camp / ".mneme" / "mempalace.yaml"
    auth.write_text(auth.read_text().replace('"4.0.0"', '"3.0.0"'))
    (w.camp / ".mneme" / "corpus.yaml").write_text(text)
    for d in ("arcs", "lore"):
        (w.camp / "docs" / d).mkdir(parents=True, exist_ok=True)
        (w.camp / "docs" / d / "a.md").write_text("# a\n")


def test_edit_is_targeted_comments_and_flow_lists_survive(w):
    _v3(w, COMMENTED)
    new, moved = move_shadowed_text(w.camp, recipe_mod.current())
    assert moved == ["arcs"]
    assert new == """\
# the Toee corpus
campaign: corp

kinds:
  npcs:
    dirs: [docs/npcs]   # flow list stays
  summaries:
    dirs: [docs/summaries]
  arcs:   # the arcs
    # why: tracked by hand
    dirs: [docs/arcs]
    files: ["docs/arcs/a.md"]
    trust: authoritative

# our own kinds
campaign_kinds:
  lore:
    dirs: [docs/lore]
    trust: reference
"""


def test_last_kind_leaves_no_campaign_kinds_key(w):
    _v3(w, "campaign: corp\nkinds:\n  npcs:\n    dirs: [docs/npcs]\n"
           "campaign_kinds:\n  arcs:\n    dirs: [docs/arcs]\n    trust: reference\n")
    new, _ = move_shadowed_text(w.camp, recipe_mod.current())
    assert new == ("campaign: corp\nkinds:\n  npcs:\n    dirs: [docs/npcs]\n"
                   "  arcs:\n    dirs: [docs/arcs]\n    trust: reference\n")


def test_no_kinds_key_creates_one_after_campaign(w):
    _v3(w, "campaign: corp\ncampaign_kinds:\n  arcs:\n    dirs: [docs/arcs]\n"
           "    trust: authoritative\n")
    new, _ = move_shadowed_text(w.camp, recipe_mod.current())
    assert new == ("campaign: corp\nkinds:\n  arcs:\n    dirs: [docs/arcs]\n"
                   "    trust: authoritative\n")
    cconfig.parse(new.encode(), recipe_mod.current(), w.camp)


def test_other_indentation_is_adapted(w):
    _v3(w, "campaign: corp\nkinds:\n    npcs:\n        dirs: [docs/npcs]\n"
           "campaign_kinds:\n  arcs:\n    dirs: [docs/arcs]\n    trust: authoritative\n")
    new, _ = move_shadowed_text(w.camp, recipe_mod.current())
    assert "    arcs:\n      dirs: [docs/arcs]\n      trust: authoritative\n" in new  # relative indent kept
    assert yaml.safe_load(new)["kinds"]["arcs"]["dirs"] == ["docs/arcs"]


@pytest.mark.parametrize("text", [
    "campaign: corp\ncampaign_kinds: {arcs: {dirs: [docs/arcs], trust: reference}}\n",
    "campaign: corp\nkinds: {npcs: {dirs: [docs/npcs]}}\ncampaign_kinds:\n  arcs:\n"
    "    dirs: [docs/arcs]\n    trust: reference\n",
    "campaign: corp\nx: &a 1\ncampaign_kinds:\n  arcs:\n    dirs: [docs/arcs]\n"
    "    trust: reference\n",
])
def test_unsupported_layouts_are_refused_for_a_hand_move(w, text):
    _v3(w, text)
    before = tree_snapshot(w.camp)
    with pytest.raises(MoveRefused):
        move_shadowed_text(w.camp, recipe_mod.current())
    with pytest.raises(CorpusRefusal, match="by hand|nothing was written"):
        publish.adopt_in_place(w.entity, "corp")
    assert tree_snapshot(w.camp) == before


def test_flow_mapping_message_names_the_hand_fix(w):
    _v3(w, "campaign: corp\ncampaign_kinds: {arcs: {dirs: [docs/arcs], trust: reference}}\n")
    with pytest.raises(MoveRefused, match="by hand") as ei:
        move_shadowed_text(w.camp, recipe_mod.current())
    assert ei.value.code == "corpus-hand-edit"


def test_failed_render_leaves_corpus_and_authority_untouched(w, monkeypatch):
    _v3(w, COMMENTED)
    before = tree_snapshot(w.camp)

    def boom(*a, **k):
        (w.camp / "mempalace.yaml").write_text("half written\n")
        raise RuntimeError("render failed")

    monkeypatch.setattr(publish._render, "write_all", boom)
    with pytest.raises(RuntimeError):
        publish.adopt_in_place(w.entity, "corp")
    assert tree_snapshot(w.camp) == before


def test_preview_conflict_is_one_clean_line(w):
    _v3(w, "campaign: corp\nkinds:\n  arcs:\n    dirs: [docs/x]\ncampaign_kinds:\n  arcs:\n"
           "    dirs: [docs/arcs]\n    trust: reference\n")
    (plan,) = publish.preview(w.entity)
    (c,) = plan.target.conflicts
    assert c.startswith("shadowed-kind: ") and "shadowed-kind" not in c[len("shadowed-kind: "):]
    assert "\n" not in c and "mneme mp preview" not in c


def test_validation_failure_is_labelled_as_such(w):
    # the moved declaration is itself invalid (a path escaping the campaign)
    _v3(w, "campaign: corp\nkinds:\n  npcs:\n    dirs: [docs/npcs]\ncampaign_kinds:\n"
           "  arcs:\n    dirs: [../arcs]\n    trust: reference\n")
    (plan,) = publish.preview(w.entity)
    (c,) = plan.target.conflicts
    assert c.startswith("corpus-invalid: ") and "\n" not in c
    assert "shadowed-kind" not in c.split(": ", 1)[0]


def test_publish_with_v3_moves_nothing_and_prints_no_move(w):
    _v3(w, COMMENTED)
    (plan,) = publish.preview(w.entity, recipe_mod.load("3.0.0"))
    assert not any("moves from" in c for c in plan.target.changed)
    assert "moves from" not in plan.line()


def test_cli_preview_discloses_the_corpus_rewrite(w):
    _v3(w, COMMENTED)
    before = tree_snapshot(w.camp)
    res = CLI.invoke(mpcli.app, ["adopt", "corp", "--here"])
    assert res.exit_code == 0, res.output
    assert "REWRITE .mneme/corpus.yaml" in res.output and "arcs" in res.output
    assert "mneme files only" not in res.output
    assert tree_snapshot(w.camp) == before


def test_cli_preview_says_when_it_would_refuse(w):
    _v3(w, "campaign: corp\ncampaign_kinds: {arcs: {dirs: [docs/arcs], trust: reference}}\n")
    res = CLI.invoke(mpcli.app, ["adopt", "corp", "--here"])
    assert res.exit_code != 0 and "would refuse" in res.output and "by hand" in res.output


def test_cli_confirm_tells_the_gm_about_the_toc(w):
    _v3(w, COMMENTED)
    res = CLI.invoke(mpcli.app, ["adopt", "corp", "--here", "--confirm"])
    assert res.exit_code == 0, res.output
    assert "wrote .mneme/corpus.yaml" in res.output
    assert "no `mneme mp refresh` is needed" in res.output


def test_mcp_preview_discloses_and_confirm_catches_refusal(w):
    _v3(w, COMMENTED)
    before = tree_snapshot(w.camp)
    res = server.adopt(w.entity, "corp", confirm=False)
    assert res["corpus_yaml"]["moves_to_kinds"] == ["arcs"]
    assert "corpus.yaml" in res["note"] and tree_snapshot(w.camp) == before

    _v3(w, "campaign: corp\ncampaign_kinds: {arcs: {dirs: [docs/arcs], trust: reference}}\n")
    before = tree_snapshot(w.camp)
    res = server.adopt(w.entity, "corp", confirm=False)
    assert "would_refuse" in res["corpus_yaml"]
    res = server.adopt(w.entity, "corp", confirm=True)
    assert "error" in res and "by hand" in res["error"]
    assert tree_snapshot(w.camp) == before


def test_branch_adopt_refused_in_the_clone_is_abandoned(w, monkeypatch):
    _v3(w, COMMENTED)
    calls = []
    wc = SimpleNamespace(path=w.root, checkout_branch=lambda b: calls.append(("co", b)),
                         abandon=lambda b: calls.append(("abandon", b)),
                         commit_all=lambda m: calls.append("commit"), push=lambda b: None)
    monkeypatch.setattr(publish, "_clone_workcopy", lambda *a, **k: wc)

    def refuse(*a, **k):
        raise CorpusRefusal("refused in the clone")

    monkeypatch.setattr(publish, "_apply_to_workcopy", refuse)
    with pytest.raises(CorpusRefusal):
        publish.adopt(w.entity, "corp")
    assert calls[-1][0] == "abandon" and "commit" not in calls


def test_preview_of_a_corpus_campaign_reports_no_baseline_exclusions(w):
    """#79: a corpus campaign renders no ignore file — the preview must not claim
    baseline exclusions, from the same recipe or an older one."""
    (plan,) = publish.preview(w.entity)
    assert plan.target.added == () and "baseline" not in plan.line()
    _v3(w, "campaign: corp\nkinds:\n  npcs:\n    dirs: [docs/npcs]\n")
    (plan,) = publish.preview(w.entity)
    assert plan.target.added == () and "baseline" not in plan.line()
