"""005 integration — membership end-to-end across discovery, find, and status (US4, US5)."""

from __future__ import annotations

import subprocess

import pytest

from hypostasis.models import MnemeIdentity
from mneme.mempalace import conform, discover, ownership
from mneme.mempalace.models import State
from mneme.mempalace.ownership import OwnerState
from tests.fixtures import entity_for_trees, make_simple_campaign

ID_A = MnemeIdentity(id="aaaaaaaa-0000-0000-0000-000000000000", label="fleet-a")
ID_B = MnemeIdentity(id="bbbbbbbb-0000-0000-0000-000000000000", label="fleet-b")


def runner_clean():
    def run(cmd):
        if len(cmd) > 1 and cmd[1] == "sync":
            return subprocess.CompletedProcess(cmd, 0, stdout="CLEAN", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    from mneme.mempalace.runner import MempalaceRunner

    return MempalaceRunner(binary="mempalace", runner=run)


def test_discover_marks_owner_state(tmp_path):
    t = tmp_path / "t1"
    mine = make_simple_campaign(t, "mine")
    ownership.write_owner(mine, ID_A)
    make_simple_campaign(t, "fresh")
    states = {r.name: r.owner_state for r in discover.discover(entity_for_trees(t, identity=ID_A))}
    assert states["mine"] is OwnerState.OWNED
    assert states["fresh"] is OwnerState.UNINTEGRATED


def test_find_excludes_foreign_resolves_owned(tmp_path):
    t1, t2 = tmp_path / "t1", tmp_path / "t2"
    a = make_simple_campaign(t1, "toee")
    ownership.write_owner(a, ID_A)
    b = make_simple_campaign(t2, "toee")
    ownership.write_owner(b, ID_B)  # foreign — must be excluded, not ambiguous
    assert discover.find(entity_for_trees(t1, t2, identity=ID_A), "toee").path == a


def test_find_foreign_only_reports_foreign(tmp_path):
    t = tmp_path / "t1"
    f = make_simple_campaign(t, "toee")
    ownership.write_owner(f, ID_B)
    with pytest.raises(discover.DiscoveryError) as ei:
        discover.find(entity_for_trees(t, identity=ID_A), "toee")
    # 006 FR-009 — the refusal names the owner, this mneme, and the remedy (it named none
    # of those before, so the only way forward was reading the source).
    msg = str(ei.value)
    assert ID_B.id in msg and ID_A.id in msg and f"identity adopt {ID_B.id}" in msg


def test_two_owned_same_name_still_ambiguous(tmp_path):
    t1, t2 = tmp_path / "t1", tmp_path / "t2"
    for tree in (t1, t2):
        ownership.write_owner(make_simple_campaign(tree, "toee"), ID_A)
    with pytest.raises(discover.DiscoveryError) as ei:
        discover.find(entity_for_trees(t1, t2, identity=ID_A), "toee")
    assert "ambiguous" in str(ei.value)


def test_status_reports_membership(tmp_path):
    # SC-006 — status surfaces owned / foreign / un-integrated, read-only.
    t = tmp_path / "t1"
    ownership.write_owner(make_simple_campaign(t, "owned"), ID_A)
    ownership.write_owner(make_simple_campaign(t, "foreign"), ID_B)
    make_simple_campaign(t, "fresh")
    report = conform.report(entity_for_trees(t, identity=ID_A), runner=runner_clean())
    owner = {r.campaign: r for r in report.rows if r.dimension == "owner"}
    assert owner["owned"].state is State.OWNED
    assert owner["foreign"].state is State.FOREIGN and ID_B.id in owner["foreign"].observed
    assert owner["fresh"].state is State.UNINTEGRATED
    # foreign/un-integrated are surfaced but not hard failures
    assert all(r.ok for r in owner.values())


def test_unverifiable_without_identity(tmp_path):
    t = tmp_path / "t1"
    ownership.write_owner(make_simple_campaign(t, "claimed"), ID_A)
    report = conform.report(entity_for_trees(t), runner=runner_clean())  # no identity
    owner = next(r for r in report.rows if r.dimension == "owner" and r.campaign == "claimed")
    assert owner.state is State.UNVERIFIABLE


# ── 006 — the fleet identity is portable across hosts (US1) ──────────────────────


def _host_config(tmp_path, tree, name="hostB.yaml") -> str:
    """A host config declaring the shared tree and NO identity — the second machine."""
    import yaml as _yaml

    raw = {
        "venv": str(tmp_path / "venv"),
        "machines": {"dgx": {"endpoint": "http://dgx:8001/v1"}},
        "data_roots": {"campaigns": [str(tree)]},
        "services": {"dgx": {"url": "http://dgx:8001/v1", "managed": False}},
        "components": {"comp": {"source": {"path": str(tmp_path / "src")}, "pin": "abc1234"}},
        "order": {"install": ["comp"], "startup": ["dgx"]},
    }
    p = tmp_path / name
    p.write_text("# host config\n" + _yaml.safe_dump(raw))
    return str(p)


def test_second_host_refuses_to_mint_then_adopts(tmp_path):
    """The GH #51 repro, end to end.

    A shared checkout whose campaigns name fleet A, on a host with no identity. Before 006
    this minted a second identity and every campaign read FOREIGN forever.
    """
    from typer.testing import CliRunner

    from mneme.cli import app

    tree = tmp_path / "campaigns"
    for name in ("toee", "obelisk"):
        ownership.write_owner(make_simple_campaign(tree, name), ID_A)
    config = _host_config(tmp_path, tree)
    before = open(config).read()
    cli = CliRunner()

    # 1. A command needing an identity refuses, names the fleet, and writes nothing.
    res = cli.invoke(app, ["integrate", "toee", "--config", config])
    assert res.exit_code != 0
    assert ID_A.id in res.output
    assert "identity adopt" in res.output and "identity mint" in res.output
    assert open(config).read() == before  # FR-005/008

    # 2. `identity show` names the same choice, and is not itself an error.
    res = cli.invoke(app, ["identity", "show", "--config", config])
    assert res.exit_code == 0
    assert "not established" in res.output and ID_A.id in res.output

    # 3. Adopting joins the fleet — and only touches the config.
    res = cli.invoke(app, ["identity", "adopt", ID_A.id, "--config", config])
    assert res.exit_code == 0, res.output
    assert "toee" in res.output and "obelisk" in res.output

    # 4. Both campaigns are now OWNED and resolvable by name — no --dir needed.
    from hypostasis import config as _cfg

    entity = _cfg.load(config)
    assert entity.mneme_identity.id == ID_A.id
    report = conform.report(entity, runner=runner_clean())
    owner = {r.campaign: r for r in report.rows if r.dimension == "owner"}
    assert owner["toee"].state is State.OWNED and owner["obelisk"].state is State.OWNED
    assert discover.find(entity, "obelisk").path == tree / "obelisk"


def test_greenfield_host_still_mints(tmp_path):
    # FR-003 — nothing to adopt, so 005's first-run experience is untouched.
    from typer.testing import CliRunner

    from mneme.cli import app

    tree = tmp_path / "campaigns"
    make_simple_campaign(tree, "fresh")
    config = _host_config(tmp_path, tree)
    res = CliRunner().invoke(app, ["integrate", "fresh", "--config", config])
    assert res.exit_code == 0, res.output
    assert "minted mneme identity" in res.output


def test_adopt_refuses_to_orphan_owned_campaigns(tmp_path):
    # FR-007 — switching fleets would strand what this host already owns.
    from typer.testing import CliRunner

    from mneme.cli import app

    tree = tmp_path / "campaigns"
    ownership.write_owner(make_simple_campaign(tree, "mine"), ID_A)
    config = _host_config(tmp_path, tree)
    cli = CliRunner()
    assert cli.invoke(app, ["identity", "adopt", ID_A.id, "--config", config]).exit_code == 0

    res = cli.invoke(app, ["identity", "adopt", ID_B.id, "--config", config])
    assert res.exit_code != 0
    assert "would orphan" in res.output and "mine" in res.output
    from hypostasis import config as _cfg

    assert _cfg.load(config).mneme_identity.id == ID_A.id  # unchanged

    res = cli.invoke(app, ["identity", "adopt", ID_B.id, "--force", "--config", config])
    assert res.exit_code == 0, res.output
    assert _cfg.load(config).mneme_identity.id == ID_B.id


# ── 006 — ownership applies to every route; aliases are unique (US4) ─────────────


def test_dir_route_no_longer_bypasses_ownership(tmp_path):
    """FR-018 — before 006, `--dir` skipped the ownership gate as a side effect of sharing
    find(). It was the only workaround for GH #51, and an undocumented take-over path."""
    t = tmp_path / "t1"
    foreign = make_simple_campaign(t, "obelisk")
    ownership.write_owner(foreign, ID_B)
    entity = entity_for_trees(t, identity=ID_A)

    with pytest.raises(discover.DiscoveryError) as by_name:
        discover.resolve(entity, "obelisk")
    with pytest.raises(discover.DiscoveryError) as by_dir:
        discover.resolve(entity, "obelisk", foreign)

    # Identical refusal whichever way the campaign was named.
    assert str(by_name.value) == str(by_dir.value)
    assert ID_B.id in str(by_dir.value) and "identity adopt" in str(by_dir.value)


def test_dir_route_still_disambiguates_owned_campaigns(tmp_path):
    # --dir keeps its real job (GH #27): pick a workspace when the name is ambiguous.
    t1, t2 = tmp_path / "t1", tmp_path / "t2"
    a = make_simple_campaign(t1, "toee")
    b = make_simple_campaign(t2, "toee")
    for c in (a, b):
        ownership.write_owner(c, ID_A)
    entity = entity_for_trees(t1, t2, identity=ID_A)
    with pytest.raises(discover.DiscoveryError):
        discover.resolve(entity, "toee")
    assert discover.resolve(entity, "toee", a).path == a


def _authority_with_alias(camp, campaign, alias):
    (camp / ".mneme").mkdir(parents=True, exist_ok=True)
    (camp / ".mneme" / "mempalace.yaml").write_text(
        f"campaign: {campaign}\nrecipe_version: '2.0.0'\n"
        f"store:\n  alias: {alias}\n"
        f"wings:\n  - name: {campaign}\n    source: .\n    trust: reference\n    rooms: []\n"
    )


def test_duplicate_store_alias_refuses_both_campaigns(tmp_path):
    # FR-016/016a — the location derives from the alias, so a duplicate means one store
    # holding two campaigns' content. Uniqueness is fleet-level, checked on both routes.
    t = tmp_path / "t1"
    a = make_simple_campaign(t, "toee")
    b = make_simple_campaign(t, "obelisk")
    for camp, name in ((a, "toee"), (b, "obelisk")):
        ownership.write_owner(camp, ID_A)
        _authority_with_alias(camp, name, "shared")
    entity = entity_for_trees(t, identity=ID_A)

    for campaign, cdir in (("toee", None), ("obelisk", None), ("toee", a)):
        with pytest.raises(discover.DiscoveryError) as ei:
            discover.resolve(entity, campaign, cdir)
        msg = str(ei.value)
        assert "shared" in msg and "toee" in msg and "obelisk" in msg


def test_distinct_aliases_are_fine(tmp_path):
    t = tmp_path / "t1"
    for name in ("toee", "obelisk"):
        camp = make_simple_campaign(t, name)
        ownership.write_owner(camp, ID_A)
        _authority_with_alias(camp, name, name)
    entity = entity_for_trees(t, identity=ID_A)
    assert discover.resolve(entity, "toee").name == "toee"
