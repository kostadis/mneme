"""`mneme mp prune` — explicit, backed-up removal of orphaned drawers (offline, stub binary)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from mneme.mempalace import backup, bringup, cli, conform, discover
from mneme.mempalace.authority import AuthorityError
from mneme.mempalace.models import State
from mneme.mempalace.runner import MempalaceError, MempalaceRunner
from tests.fixtures import STUB, entity_for, make_greenfield_campaign


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    log = tmp_path / "stub.log"
    monkeypatch.setenv("MNEME_STUB_LOG", str(log))
    monkeypatch.setenv("MNEME_STUB_APPLY_STATE", str(tmp_path / "applied"))
    runner = MempalaceRunner(binary=str(STUB))
    root = tmp_path / "campaigns"
    make_greenfield_campaign(root, "stormhaven")
    entity = entity_for(root)
    bringup.bringup(entity, "stormhaven", runner=runner, do_backup=False)
    log.write_text("")  # only what prune does from here
    monkeypatch.setattr(cli, "_load_or_exit", lambda config: entity)
    monkeypatch.setattr(MempalaceRunner, "for_entity", classmethod(lambda c, e, **k: runner))
    return entity, log, runner


def _syncs(log: Path) -> list[str]:
    return [ln for ln in log.read_text().splitlines() if " sync " in f" {ln} " or ln == "BACKUP"]


def _fake_backup(monkeypatch, log: Path):
    real = backup.backup

    def spy(*a, **k):
        with open(log, "a") as fh:
            fh.write("BACKUP\n")
        return real(*a, **k)

    monkeypatch.setattr(backup, "backup", spy)


def _prune(*args):
    return CliRunner().invoke(cli.app, ["prune", "stormhaven", *args])


def test_preview_prints_counts_and_never_applies(world, monkeypatch):
    _e, log, _r = world
    monkeypatch.setenv("MNEME_STUB_SYNC", "2,1,4")
    res = _prune()
    assert res.exit_code == 0, res.output
    assert "would remove 3 orphaned drawers (2 missing, 1 gitignored)" in res.output
    assert "/stub/gone.md" in res.output  # top sources relayed
    assert "4 out-of-scope drawers are NOT touched" in res.output and "regenerate" in res.output
    assert "`mneme mp prune stormhaven --confirm --expect 3`" in res.output
    assert "--apply" not in log.read_text()


def test_nothing_to_prune(world, monkeypatch):
    _e, log, _r = world
    for args in (["--confirm", "--expect", "0"], []):
        res = _prune(*args)
        assert res.exit_code == 0 and "nothing to prune" in res.output
    assert "--apply" not in log.read_text()


def test_confirm_backs_up_then_applies_then_verifies(world, monkeypatch):
    _e, log, _r = world
    monkeypatch.setenv("MNEME_STUB_SYNC", "2,1")
    _fake_backup(monkeypatch, log)
    res = _prune("--confirm", "--expect", "3")
    assert res.exit_code == 0, res.output
    kinds = [
        "BACKUP" if ln == "BACKUP" else ("apply" if "--apply" in ln else "dry")
        for ln in _syncs(log)
    ]
    assert kinds == ["dry", "BACKUP", "apply", "dry"]
    assert "backed up bindings" in res.output
    assert "removed 3 orphaned drawers" in res.output
    assert "before: 2 missing, 1 gitignored  after: 0 missing, 0 gitignored" in res.output
    assert "verified" in res.output


def test_no_backup_skips_backup(world, monkeypatch):
    _e, log, _r = world
    monkeypatch.setenv("MNEME_STUB_SYNC", "1,0")
    _fake_backup(monkeypatch, log)
    res = _prune("--confirm", "--expect", "1", "--no-backup")
    assert res.exit_code == 0, res.output
    assert "BACKUP" not in log.read_text() and "--apply" in log.read_text()
    assert "skipping backup" in res.output


def test_backup_failure_aborts_without_apply(world, monkeypatch):
    _e, log, _r = world
    monkeypatch.setenv("MNEME_STUB_SYNC", "1,0")

    def boom(*a, **k):
        raise backup.BackupError("no room")

    monkeypatch.setattr(backup, "backup", boom)
    res = _prune("--confirm", "--expect", "1")
    assert res.exit_code == cli.EXIT_RUNTIME
    assert "FAIL prune: no room" in res.output
    assert "--apply" not in log.read_text()


def test_post_check_nonzero_exits_nonzero(world, monkeypatch):
    _e, _log, _r = world
    monkeypatch.setenv("MNEME_STUB_SYNC", "2,0")
    monkeypatch.delenv("MNEME_STUB_APPLY_STATE")  # the stub never flips to clean
    res = _prune("--confirm", "--expect", "2", "--no-backup")
    assert res.exit_code == cli.EXIT_RUNTIME
    assert "FAIL prune: 2 orphaned drawers remain" in res.output


def test_apply_failure_is_reported(world, monkeypatch):
    _e, _log, _r = world
    # dry-run sees orphans, then the apply exits 1
    monkeypatch.setenv("MNEME_STUB_SYNC", "applyrc1")
    runner = MempalaceRunner(binary=str(STUB))
    from mneme.mempalace.runner import SyncCheck

    real = runner.sync

    def sync(path, palace=None, roots=(), apply=False):
        if not apply:
            return SyncCheck(True, 1, 0, 0)
        return real(path, palace, roots, apply=True)

    monkeypatch.setattr(MempalaceRunner, "for_entity", classmethod(lambda c, e, **k: runner))
    monkeypatch.setattr(runner, "sync", sync)
    res = _prune("--confirm", "--expect", "1")
    assert res.exit_code == cli.EXIT_RUNTIME
    assert "FAIL prune:" in res.output and "sync --apply" in res.output
    assert "backed up bindings → " in res.output  # the backup path survives the failure


def test_scope_args_identical_to_index_row(world, monkeypatch):
    entity, log, runner = world
    monkeypatch.setenv("MNEME_STUB_SYNC", "1,0")
    calls: list = []
    real = conform.sync_scope

    def spy(ref, cfg):
        calls.append(1)
        return real(ref, cfg)

    monkeypatch.setattr(conform, "sync_scope", spy)
    conform.report(entity, campaign="stormhaven", runner=runner)
    status_syncs = [ln for ln in _syncs(log)]
    log.write_text("")
    assert _prune().exit_code == 0
    prune_syncs = _syncs(log)
    assert len(calls) == 2  # status row + prune both go through the one helper
    assert status_syncs == prune_syncs  # byte-identical argv (--palace, path, --root set)
    assert "--palace" in prune_syncs[0] and "--dry-run" in prune_syncs[0]


@pytest.mark.parametrize("kind", ["discovery", "authority", "oserror", "mempalace", "backup"])
def test_error_kinds_print_fail_prune(world, monkeypatch, kind):
    from mneme.mempalace import prune as prune_mod

    exc = {
        "discovery": discover.DiscoveryError("no such campaign"),
        "authority": AuthorityError(["no store pointer"]),
        "oserror": OSError("disk"),
        "mempalace": MempalaceError("boom"),
        "backup": backup.BackupError("nope"),
    }[kind]

    def raiser(*a, **k):
        raise exc

    monkeypatch.setattr(prune_mod, "prune", raiser)
    res = _prune()
    assert res.exit_code == cli.EXIT_RUNTIME and "FAIL prune:" in res.output
    assert isinstance(res.exception, SystemExit)
    if kind == "authority":
        assert "no store pointer" in res.output


def test_missing_store_fails_clearly(world, monkeypatch):
    import shutil

    entity, _log, _r = world
    ref = discover.resolve(entity, "stormhaven", None)
    from mneme.mempalace import authority

    cfg = authority.load(ref.path, mempalace_root=None)
    shutil.rmtree(cfg.store.path)
    res = _prune()
    assert res.exit_code == cli.EXIT_RUNTIME
    assert "FAIL prune:" in res.output and "store missing" in res.output


def test_no_store_pointer_fails_clearly(tmp_path, monkeypatch):
    from tests.fixtures import make_campaigns

    root = make_campaigns(tmp_path / "campaigns")  # `full` has an authority, no store pointer
    monkeypatch.setattr(cli, "_load_or_exit", lambda config: entity_for(root))
    res = CliRunner().invoke(cli.app, ["prune", "full"])
    assert res.exit_code == cli.EXIT_RUNTIME
    assert "FAIL prune:" in res.output and "no store pointer" in res.output


def test_status_note_recommends_prune_for_orphans_regenerate_for_oos(world, monkeypatch):
    entity, _log, runner = world

    def note(mode):
        monkeypatch.setenv("MNEME_STUB_SYNC", mode)
        rows = conform.report(entity, campaign="stormhaven", runner=runner).for_campaign(
            "stormhaven"
        )
        row = next(r for r in rows if r.dimension == "index")
        assert row.state is State.STALE
        return row.note

    orphans = note("2,1,0")
    assert "mneme mp prune stormhaven" in orphans and "--confirm" in orphans
    assert "refresh" not in orphans and "regenerate" not in orphans
    oos = note("0,0,5")
    assert "regenerate stormhaven --confirm" in oos and "prune" not in oos
    both = note("1,0,5")
    assert "prune" in both and "regenerate" in both


def test_confirm_requires_expect(world, monkeypatch):
    _e, log, _r = world
    monkeypatch.setenv("MNEME_STUB_SYNC", "2,0")
    res = _prune("--confirm")
    assert res.exit_code == cli.EXIT_RUNTIME
    assert "--expect" in res.output and "preview" in res.output
    assert log.read_text() == ""  # nothing ran


def test_count_mismatch_aborts_before_backup_and_apply(world, monkeypatch):
    _e, log, _r = world
    monkeypatch.setenv("MNEME_STUB_SYNC", "5,0")
    _fake_backup(monkeypatch, log)
    res = _prune("--confirm", "--expect", "2")
    assert res.exit_code == cli.EXIT_RUNTIME
    assert "orphan set changed since preview (2 → 5) — re-run the preview" in res.output
    text = log.read_text()
    assert "BACKUP" not in text and "--apply" not in text


def _patched_sync(monkeypatch, runner, **by_mode):
    real = runner.sync

    def sync(path, palace=None, roots=(), apply=False):
        got = by_mode.get("apply" if apply else "dry")
        return got if got is not None else real(path, palace, roots, apply=apply)

    monkeypatch.setattr(runner, "sync", sync)


def test_post_apply_removed_more_than_approved_fails(world, monkeypatch):
    from mneme.mempalace.runner import SyncCheck

    _e, _log, runner = world
    monkeypatch.setenv("MNEME_STUB_SYNC", "2,0")
    _patched_sync(monkeypatch, runner, apply=SyncCheck(True, 5, 0, 0))
    res = _prune("--confirm", "--expect", "2", "--no-backup")
    assert res.exit_code == cli.EXIT_RUNTIME
    assert "removed 5 drawers but only 2 were approved" in res.output


def test_preview_does_not_imply_top_list_is_complete(world, monkeypatch):
    from mneme.mempalace.runner import SyncCheck

    _e, _log, runner = world
    _patched_sync(
        monkeypatch, runner, dry=SyncCheck(True, 9, 0, 0, "", ("a.md  (3)", "b.md  (2)"))
    )
    res = _prune()
    assert "… and 4 more drawers from sources mempalace did not list" in res.output
    _patched_sync(monkeypatch, runner, dry=SyncCheck(True, 5, 0, 0, "", ("a.md  (3)", "b.md  (2)")))
    assert "more drawers" not in _prune().output


def test_verify_failure_still_shows_backup_path(world, monkeypatch):
    _e, _log, runner = world
    monkeypatch.setenv("MNEME_STUB_SYNC", "2,0")
    monkeypatch.delenv("MNEME_STUB_APPLY_STATE")  # post-check stays dirty
    res = _prune("--confirm", "--expect", "2")
    assert res.exit_code == cli.EXIT_RUNTIME
    assert "backed up bindings → " in res.output and "FAIL prune:" in res.output


def test_ignored_flags_warn_in_preview(world):
    res = _prune("--no-backup")
    assert "ignored without --confirm" in res.output
    res = _prune("--expect", "3")
    assert "ignored without --confirm" in res.output


@pytest.mark.parametrize("name", ["prune-test", "regenerate-x"])
def test_restore_advice_matches_commands_not_campaign_names(tmp_path, monkeypatch, name):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("MNEME_STUB_LOG", str(tmp_path / "stub.log"))
    runner = MempalaceRunner(binary=str(STUB))
    root = tmp_path / "campaigns"
    make_greenfield_campaign(root, name)
    entity = entity_for(root)
    bringup.bringup(entity, name, runner=runner, do_backup=True)
    import shutil

    from mneme.mempalace import authority

    store = authority.load(root / name, mempalace_root=None).store.path
    shutil.rmtree(store)
    monkeypatch.setattr(cli, "_load_or_exit", lambda config: entity)
    monkeypatch.setattr(MempalaceRunner, "for_entity", classmethod(lambda c, e, **k: runner))
    from mneme.mempalace import embedder_guard
    from tests.unit.test_mp_embedder_guard import prober_for

    monkeypatch.setattr(embedder_guard, "default_prober", prober_for(384))
    monkeypatch.setenv("MNEME_STUB_SYNC", "2,0,0")
    res = CliRunner().invoke(cli.app, ["restore", name])
    advice = [ln for ln in res.output.splitlines() if "recommend:" in ln]
    assert any(f"mneme mp prune {name}`" in a for a in advice), res.output
    assert not any("mneme mp regenerate" in a for a in advice), res.output
    monkeypatch.setenv("MNEME_STUB_SYNC", "0,0,3")
    shutil.rmtree(store, ignore_errors=True)
    res = CliRunner().invoke(cli.app, ["restore", name])
    advice = [ln for ln in res.output.splitlines() if "recommend:" in ln]
    assert any(f"mneme mp regenerate {name} --confirm`" in a for a in advice), res.output
    assert not any("mneme mp prune" in a for a in advice), res.output
