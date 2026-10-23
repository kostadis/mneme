"""Wing-model mining paths refuse corpus campaigns (feature 007, T017).

A corpus campaign keeps a ROOT `mempalace.yaml`, so `_existing_wing_dirs` returns the
campaign root and a wing-model `mine <root>` would mine the whole tree: the fail-open this
feature removes. Every assertion reads the stub log for a `mine` verb."""

from __future__ import annotations

import subprocess
import sys

import pytest

from mneme.corpus.config import CORPUS_REFUSAL
from mneme.mempalace import authority, backup, bootstrap, conform, provision, recipe, refresh
from mneme.mempalace.models import State
from mneme.mempalace.runner import MempalaceError, MempalaceRunner
from tests.fixtures import STUB, add_store_pointer, entity_for, make_campaigns


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    log = tmp_path / "log"
    monkeypatch.setenv("MNEME_STUB_LOG", str(log))

    def run(cmd):
        return subprocess.run([sys.executable, str(STUB), *cmd[1:]], capture_output=True, text=True)

    root = make_campaigns(tmp_path / "campaigns")
    camp = root / "corp"
    (camp / ".mneme").mkdir(parents=True)
    (camp / "docs").mkdir()
    (camp / "docs" / "a.md").write_text("a\n")
    (camp / "mempalace.yaml").write_text("wing: corp\nrooms: []\n")  # root => whole tree
    (camp / ".mneme" / "mempalace.yaml").write_text(
        'campaign: corp\nrecipe_version: "3.0.0"\nstore:\n  alias: corp\n'
    )
    (camp / ".mneme" / "corpus.yaml").write_text(
        "campaign: corp\nkinds:\n  npcs:\n    dirs: [docs]\n"
    )
    add_store_pointer(root, "full")
    return MempalaceRunner("mempalace", run), root, camp, log


def mine_lines(log):
    return [ln for ln in (log.read_text().splitlines() if log.exists() else []) if " mine " in
            f" {ln} " or ln.startswith("mine")]


def test_authority_without_wings_loads_for_a_corpus_campaign(world):
    _, _, camp, _ = world
    cfg = authority.load(camp)
    assert cfg.campaign == "corp" and cfg.wings == ()


def test_refresh_refuses_and_never_mines(world):
    runner, root, camp, log = world
    res = {r.campaign: r for r in refresh.refresh(entity_for(root), runner=runner)}
    assert res["corp"].failed and CORPUS_REFUSAL in res["corp"].error
    assert not res["corp"].skipped
    lines = mine_lines(log)
    assert lines  # the other (wing-model) campaigns still mine
    assert not any(str(camp) in ln for ln in lines)


def test_refresh_one_corpus_campaign_issues_no_stub_call_at_all(world):
    runner, root, camp, log = world
    (r,) = refresh.refresh(entity_for(root), campaign="corp", runner=runner)
    assert r.failed and CORPUS_REFUSAL in r.line()
    assert not log.exists() or log.read_text() == ""


def test_first_mine_refuses(world):
    runner, root, camp, log = world
    cfg = authority.load(camp)
    with pytest.raises(MempalaceError, match="mining is driven by .mneme/corpus.yaml"):
        provision.first_mine(cfg, camp, runner)
    assert not log.exists() or log.read_text() == ""


def test_consolidate_refuses_instead_of_folding_the_root_as_a_wing(world):
    _, _, camp, _ = world
    with pytest.raises(MempalaceError, match="corpus campaign"):
        bootstrap.consolidate_config("corp", camp, recipe.current())


def test_check_dir_returns_a_failing_row_and_does_not_mine(world):
    runner, _, camp, log = world
    rep = conform.check_dir(camp, runner=runner)
    (row,) = rep.rows
    assert row.state == State.INVALID_CONFIG and CORPUS_REFUSAL in row.note
    assert rep.exit_code() != 0
    assert not mine_lines(log)


def test_regenerate_refuses_before_deleting_the_store(world, tmp_path):
    runner, root, camp, log = world
    entity = entity_for(root, mempalace=tmp_path / "mp")
    store = tmp_path / "mp" / "palaces" / "corp"
    store.mkdir(parents=True)
    (store / "keep").write_text("precious")
    with pytest.raises(MempalaceError, match="corpus campaign"):
        backup.regenerate(entity, "corp", runner=runner)
    assert (store / "keep").read_text() == "precious"
    assert not mine_lines(log)


def test_wing_model_campaigns_are_unaffected(world):
    runner, root, _, log = world
    (r,) = refresh.refresh(entity_for(root), campaign="full", runner=runner)
    assert not r.failed and not r.skipped
    assert mine_lines(log)
