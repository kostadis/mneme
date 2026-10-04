"""GH #31 — skipped files at mine time: parser, tee runner, record, report, status row."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys

import pytest
from typer.testing import CliRunner

from mneme.mcp import server as mcp_server
from mneme.mempalace import backup, bringup, cli, conform, mine_record, provision, refresh
from mneme.mempalace import embedder_guard as guard
from mneme.mempalace.mine_report import parse_skips, warning_lines
from mneme.mempalace.models import FAIL_STATES, ConformanceReport, ConformanceRow, State
from mneme.mempalace.runner import MempalaceError, MempalaceRunner, _run_stream
from tests.fixtures import STUB, entity_for, make_greenfield_campaign

CHUNK_NEW = (
    "  ! [skip] {name:50} produced 812 chunks (> 500); raise via --max-chunks-per-file or "
    "MEMPALACE_MAX_CHUNKS_PER_FILE (set 0 to disable), or add to SKIP_FILENAMES if this is a "
    "generated artifact"
)
CHUNK_OLD = "  ! [skip] {name:50} produced 812 chunks (> 500); add to SKIP_FILENAMES or .gitignore"


# ── parser ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("fmt", [CHUNK_NEW, CHUNK_OLD])
def test_parse_chunk_cap_both_versions_padding_stripped(fmt):
    (n,) = parse_skips(fmt.format(name="bible.md"))
    assert (n.name, n.kind) == ("bible.md", "chunk_cap")
    assert "812 chunks (> 500" in n.detail and n.line.startswith("! [skip] bible.md")


def test_parse_name_with_spaces_and_truncation():
    long = "x" * 80
    (a,) = parse_skips(CHUNK_NEW.format(name="Session 12 recap.md"))
    (b,) = parse_skips(CHUNK_NEW.format(name=long[:50]))
    assert a.name == "Session 12 recap.md" and b.name == "x" * 50


def test_parse_skip_variants():
    text = "\n".join(
        [
            "  SKIP: docs/link.md (symlink)",
            "  SKIP: pipe (not a regular file)",
            "  SKIP: huge.pdf (12.5 MB) exceeds 10 MB limit",
            "  SKIP: gone.md (stat error: No such file (x))",
        ]
    )
    got = [(n.name, n.kind) for n in parse_skips(text)]
    assert got == [
        ("docs/link.md", "symlink"),
        ("pipe", "not_regular"),
        ("huge.pdf", "too_large"),
        ("gone.md", "stat_error"),
    ]


def test_parse_purge_failure_both_shapes():
    miner = (
        "  ! [skip] {n:50} stale-drawer purge failed (OSError('disk'));"
        " leaving existing drawers untouched, will retry on the next mine"
    ).format(n="canon.md")
    convo = (
        "  ! [skip] stale-drawer purge failed for '/c/a.md' (OSError('x')); "
        "leaving existing drawers untouched, will retry on the next mine"
    )
    a, b = parse_skips(miner + "\n" + convo)
    assert (a.name, a.kind) == ("canon.md", "purge_failed")
    assert (b.name, b.kind) == ("/c/a.md", "purge_failed")


def test_parse_summary_count_fallback_only_when_unnamed():
    summary = "  Files skipped (chunk cap 500): 3 (raise via --max-chunks-per-file)"
    named = CHUNK_NEW.format(name="a.md")
    notices = parse_skips(named + "\n" + summary)
    assert [n.kind for n in notices] == ["chunk_cap", "other"]
    assert "3 file(s)" in notices[1].detail and "only 1" in notices[1].detail
    assert [n.kind for n in parse_skips("\n".join([named] * 3) + "\n" + summary)] == [
        "chunk_cap"
    ] * 3


# Verbatim emitters, copied from the f-strings in ~/src/Mempalace (kostadis-dev) and the 46fcfc2
# pin; each is formatted with sample values and must parse to the right kind.
REAL_FORMATS = [
    # miner.py:1954-1957
    ("chunk_cap", lambda: (
        f"  ! [skip] {'a.md'[:50]:50} produced {812} chunks "
        f"(> {500}); raise via --max-chunks-per-file or "
        f"MEMPALACE_MAX_CHUNKS_PER_FILE (set 0 to disable), or add to "
        f"SKIP_FILENAMES if this is a generated artifact")),
    # miner.py:938-939 @ 46fcfc2
    ("chunk_cap", lambda: (
        f"  ! [skip] {'a.md'[:50]:50} produced {812} chunks "
        f"(> {500}); add to SKIP_FILENAMES or .gitignore")),
    # miner.py:2081-2083
    ("purge_failed", lambda: (
        f"  ! [skip] {'a.md'[:50]:50} stale-drawer purge "
        f"failed ({OSError('x')!r}); leaving existing drawers untouched, will retry "
        f"on the next mine")),
    # convo_miner.py:945-947
    ("purge_failed", lambda: (
        f"  ! [skip] stale-drawer purge failed for {'/c/a.md'!r} "
        f"({OSError('x')!r}); leaving existing drawers untouched, will retry "
        f"on the next mine")),
    # miner.py:2312 / convo_miner.py:626
    ("symlink", lambda: f"  SKIP: {'d/a.md'} (symlink)"),
    # miner.py:2330 / convo_miner.py:642
    ("not_regular", lambda: f"  SKIP: {'a.md'} (not a regular file)"),
    # miner.py:2337-2338 / convo_miner.py:649-650
    ("too_large", lambda: (
        f"  SKIP: {'a.md'} ({600 * 1024 * 1024 / (1024 * 1024):.1f} MB)"
        f" exceeds {500 * 1024 * 1024 // (1024 * 1024)} MB limit")),
    # miner.py:2349 / convo_miner.py:659
    ("stat_error", lambda: f"  SKIP: {'a.md'} (stat error: {'Permission denied'})"),
]


@pytest.mark.parametrize(("kind", "make"), REAL_FORMATS)
def test_every_real_emitter_format_parses(kind, make):
    (n,) = parse_skips(make())
    assert n.kind == kind and n.name.endswith("a.md")


def test_too_large_detail_names_limit():
    (n,) = parse_skips("  SKIP: a.md (600.0 MB) exceeds 500 MB limit")
    assert n.kind == "too_large" and "500 MB limit" in n.detail


def test_parse_garbage_is_nothing():
    assert parse_skips("") == []
    assert parse_skips("Mining 4 files\n  [ok] a.md\nFiles skipped (already filed): 2") == []


# ── stream (tee) runner ──────────────────────────────────────────────────────

CHILD = (
    "import os,sys;print('out-line');print('err-line',file=sys.stderr);"
    "print(os.environ.get('X_OVERLAY'),os.environ.get('PYTHONUNBUFFERED'));sys.exit({rc})"
)


def test_stream_echoes_and_captures(capsys):
    cp = _run_stream([sys.executable, "-c", CHILD.format(rc=0)], env={"X_OVERLAY": "yes"})
    seen = capsys.readouterr()
    assert "out-line" in seen.out and "err-line" in seen.err
    assert cp.returncode == 0
    assert "out-line" in cp.stdout and "err-line" in cp.stderr
    assert "yes 1" in cp.stdout  # overlay + PYTHONUNBUFFERED applied


def test_stream_mine_parses_skips_and_failure_has_real_tail(capsys):
    script = (
        "import sys;print('  SKIP: a.pdf (9.0 MB)',file=sys.stderr);sys.exit({rc})"
    )
    def tee(rc):
        return lambda cmd: _run_stream([sys.executable, "-c", script.format(rc=rc)])

    ok = MempalaceRunner(binary=sys.executable, runner=tee(0)).mine(".")
    assert [n.kind for n in ok.skips] == ["too_large"]
    bad = MempalaceRunner(binary=sys.executable, runner=tee(3))
    with pytest.raises(MempalaceError, match=r"rc 3.*a\.pdf"):
        bad.mine(".")
    capsys.readouterr()


# ── world: stub binary, real bring-up ────────────────────────────────────────


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("MNEME_STUB_LOG", str(tmp_path / "stub.log"))
    root = tmp_path / "campaigns"
    make_greenfield_campaign(root, "stormhaven")
    store = tmp_path / "home" / ".mempalace" / "palaces" / "stormhaven"
    return entity_for(root), MempalaceRunner(binary=str(STUB)), store


SKIPS = CHUNK_NEW.format(name="bible.md") + "\nout:" + CHUNK_OLD.format(name="other.md")


def test_bringup_records_aggregated_skips_and_warns(world, monkeypatch):
    entity, runner, store = world
    monkeypatch.setenv("MNEME_STUB_MINE_SKIPS", SKIPS)
    report = bringup.bringup(entity, "stormhaven", runner=runner, do_backup=False)
    assert report.ready and report.exit_code() == 0
    rec = mine_record.read(store)
    assert rec is not None and rec.campaign == "stormhaven"
    assert rec.names.count("bible.md") >= 1 and "other.md" in rec.names
    assert len(rec.wings) >= 1  # every mined wing keyed
    lines = warning_lines("stormhaven", report.skips)
    assert lines[0].startswith("WARN index gap: stormhaven/")
    assert any("MEMPALACE_MAX_CHUNKS_PER_FILE in hypostasis.yaml env:" in ln for ln in lines)


def test_clean_mine_writes_empty_lists(world):
    entity, runner, store = world
    bringup.bringup(entity, "stormhaven", runner=runner, do_backup=False)
    doc = json.loads((store / mine_record.FILENAME).read_text())
    assert doc["schema"] == 1 and doc["wings"] and all(v == [] for v in doc["wings"].values())
    assert doc["mined_at"].endswith("+00:00")


def test_dry_run_does_not_write_and_failure_records_failed(world, monkeypatch):
    entity, runner, store = world
    bringup.bringup(entity, "stormhaven", runner=runner, do_backup=False)
    path = store / mine_record.FILENAME
    path.unlink()
    from mneme.mempalace import authority

    cfg = authority.load(entity_campaign(entity, "stormhaven"))
    provision.first_mine(cfg, entity_campaign(entity, "stormhaven"), runner, dry_run=True)
    assert not path.exists()
    path.write_text(json.dumps({"schema": 1, "mined_at": "t", "campaign": "c", "wings": {}}))
    failing = MempalaceRunner(
        binary="x", runner=lambda c: subprocess.CompletedProcess(c, 1, "", "boom")
    )
    with pytest.raises(MempalaceError):
        provision.first_mine(cfg, entity_campaign(entity, "stormhaven"), failing)
    # a failed (non-dry) mine replaces any stale record with a status=failed one
    assert mine_record.read(path.parent).status == "failed"


def entity_campaign(entity, name):
    return entity.data_roots["campaigns"][0] / name if hasattr(entity, "data_roots") else None


def test_refresh_aggregates_per_wing_and_warns_without_exit_change(world, monkeypatch):
    entity, runner, store = world
    bringup.bringup(entity, "stormhaven", runner=runner, do_backup=False)
    monkeypatch.setenv("MNEME_STUB_MINE_SKIPS", "  SKIP: a.pdf (9.0 MB) exceeds 500 MB limit")
    (res,) = refresh.refresh(entity, campaign="stormhaven", runner=runner)
    assert not res.failed
    rec = mine_record.read(store)
    assert rec is not None and sum(len(v) for v in rec.wings.values()) == len(res.skips) >= 1
    assert any(ln.startswith("WARN index gap: stormhaven/") for ln in res.warnings())
    monkeypatch.setattr(cli, "_load_or_exit", lambda config: entity)
    monkeypatch.setattr(MempalaceRunner, "for_entity", classmethod(lambda c, e, **k: runner))
    out = CliRunner().invoke(cli.app, ["refresh", "stormhaven"])
    assert out.exit_code == 0 and "WARN index gap: stormhaven/" in out.output


def test_refresh_dry_run_does_not_record(world, monkeypatch):
    entity, runner, store = world
    bringup.bringup(entity, "stormhaven", runner=runner, do_backup=False)
    (store / mine_record.FILENAME).unlink()
    refresh.refresh(entity, campaign="stormhaven", runner=runner, dry_run=True)
    assert not (store / mine_record.FILENAME).exists()


def test_cli_bringup_prints_warnings_exit_zero(world, monkeypatch):
    entity, runner, _ = world
    monkeypatch.setenv("MNEME_STUB_MINE_SKIPS", CHUNK_NEW.format(name="bible.md"))
    monkeypatch.setattr(cli, "_load_or_exit", lambda config: entity)
    monkeypatch.setattr(MempalaceRunner, "for_entity", classmethod(lambda c, e, **k: runner))
    out = CliRunner().invoke(cli.app, ["bringup", "stormhaven", "--no-backup"])
    assert out.exit_code == 0, out.output
    assert "WARN index gap: stormhaven/" in out.output and "bible.md" in out.output
    assert "split the file" in out.output


def test_record_write_is_atomic_no_temp_left(tmp_path):
    mine_record.write(tmp_path / "s", "c", ["w"], ())
    mine_record.write(tmp_path / "s", "c", ["w"], ())
    assert sorted(p.name for p in (tmp_path / "s").iterdir()) == [mine_record.FILENAME]


# ── store lifecycle ──────────────────────────────────────────────────────────


def test_record_not_a_vector_artifact_nor_legacy_nor_in_backup(world):
    entity, runner, store = world
    bringup.bringup(entity, "stormhaven", runner=runner, do_backup=True)
    assert (store / mine_record.FILENAME).is_file()
    assert guard.non_turbovec_artifacts(store) == []
    from mneme.mempalace import health

    assert health.inspect(store).legacy_files == ()
    assert store / mine_record.FILENAME not in health.inspect(store).bindings_files
    assert health.drop_legacy(store) == [] and (store / mine_record.FILENAME).is_file()
    snap = backup.latest_backup(entity, "stormhaven")
    assert not list(snap.rglob(mine_record.FILENAME))


def test_regenerate_rewrites_record(world, monkeypatch):
    entity, runner, store = world
    bringup.bringup(entity, "stormhaven", runner=runner, do_backup=False)
    monkeypatch.setenv("MNEME_STUB_MINE_SKIPS", "  SKIP: a.pdf (9.0 MB) exceeds 500 MB limit")
    fm = backup.regenerate(entity, "stormhaven", runner=runner, prober=lambda *a, **k: 384)
    assert fm.skips
    rec = mine_record.read(store)
    assert rec is not None and "a.pdf" in rec.names
    shutil.rmtree(store)  # wiped store: record gone, status must say unknown, not clean
    assert mine_record.read(store) is None


# ── status row ───────────────────────────────────────────────────────────────


def _gaps(entity, runner):
    rows = conform.report(entity, campaign="stormhaven", runner=runner).rows
    return next(r for r in rows if r.dimension == "gaps")


def test_gaps_row_states(world, monkeypatch):
    entity, runner, store = world
    bringup.bringup(entity, "stormhaven", runner=runner, do_backup=False)
    path = store / mine_record.FILENAME
    row = _gaps(entity, runner)
    assert row.state is State.CONFORMANT and "no files skipped at last mine" in row.note

    refresh.refresh(entity, campaign="stormhaven", runner=runner)  # still clean
    many = "\n".join(f"  SKIP: f{i}.pdf (9.0 MB) exceeds 500 MB limit" for i in range(9))
    monkeypatch.setenv("MNEME_STUB_MINE_SKIPS", many)
    refresh.refresh(entity, campaign="stormhaven", runner=runner)
    row = _gaps(entity, runner)
    assert row.state is State.INDEX_GAPS and not row.ok and row.state not in FAIL_STATES
    assert "skipped at last mine: f0.pdf" in row.note and "more)" in row.note
    assert conform.format_row(row).startswith("??")

    path.write_text("{not json")
    row = _gaps(entity, runner)
    assert row.state is State.INDEX_UNVERIFIED and "unreadable" in row.note

    path.unlink()
    row = _gaps(entity, runner)
    assert row.state is State.INDEX_UNVERIFIED and "no mine recorded by mneme yet" in row.note


def test_strict_fails_on_gaps_only_under_strict():
    rep = ConformanceReport(rows=(ConformanceRow("c", "gaps", State.INDEX_GAPS, note="x"),))
    assert rep.exit_code() == 0 and rep.exit_code(strict=True) == 1


def test_mcp_status_ok_false_for_gaps(world, monkeypatch):
    entity, runner, _ = world
    bringup.bringup(entity, "stormhaven", runner=runner, do_backup=False)
    monkeypatch.setenv("MNEME_STUB_MINE_SKIPS", "  SKIP: a.pdf (9.0 MB) exceeds 500 MB limit")
    refresh.refresh(entity, campaign="stormhaven", runner=runner)
    monkeypatch.setattr(MempalaceRunner, "for_entity", classmethod(lambda c, e, **k: runner))
    rows = mcp_server.status(entity, "stormhaven")
    gaps = next(r for r in rows if r["dimension"] == "gaps")
    assert gaps["state"] == "index_gaps" and gaps["ok"] is False


def test_restore_freshness_ignores_gaps_dimension():
    from mneme.mempalace import backup as b

    assert "gaps" not in b._FRESHNESS_DIMS and State.INDEX_GAPS not in b._NOT_FRESH


# ── review fixes ─────────────────────────────────────────────────────────────


def test_stream_invalid_utf8_and_big_output_does_not_hang():
    child = (
        "import sys\n"
        "for s in (sys.stdout, sys.stderr):\n"
        "    s.buffer.write(b'bad \\xff\\xfe bytes\\n' + b'x' * 200000 + b'\\n'); s.flush()\n"
    )
    import concurrent.futures as cf

    with cf.ThreadPoolExecutor(1) as ex:
        cp = ex.submit(_run_stream, [sys.executable, "-c", child]).result(timeout=30)
    assert cp.returncode == 0
    assert len(cp.stdout) > 128 * 1024 and len(cp.stderr) > 128 * 1024
    assert "\ufffd" in cp.stdout


def _failing_second_wing(runner):
    """A runner whose 2nd mine fails after the 1st printed a skip."""
    calls = []

    def run(cmd):
        calls.append(cmd)
        if len(calls) == 1:
            return subprocess.CompletedProcess(
                cmd, 0, "", "  SKIP: a.pdf (9.0 MB) exceeds 500 MB limit"
            )
        return subprocess.CompletedProcess(cmd, 1, "", "kaboom")

    return MempalaceRunner(binary="mp", runner=run)


def test_failed_refresh_keeps_partial_skips_and_records_failure(world, monkeypatch):
    entity, runner, store = world
    bringup.bringup(entity, "stormhaven", runner=runner, do_backup=False)
    (res,) = refresh.refresh(
        entity, campaign="stormhaven", runner=_failing_second_wing(runner)
    )
    assert res.failed and res.skips and any("a.pdf" in ln for ln in res.warnings())
    rec = mine_record.read(store)
    assert rec.status == "failed" and "kaboom" in rec.error and "a.pdf" in rec.names
    row = _gaps(entity, runner)
    assert row.state is State.INDEX_UNVERIFIED
    assert "last mine failed at" in row.note and "partial skips: a.pdf" in row.note


def test_failed_first_mine_reports_partial_skips_and_failed_record(world):
    entity, runner, store = world
    bringup.bringup(entity, "stormhaven", runner=runner, do_backup=False)
    report = bringup.bringup(
        entity, "stormhaven", runner=_failing_second_wing(runner), do_backup=False
    )
    assert not report.ready and report.skips
    assert mine_record.read(store).status == "failed"


def test_record_write_failure_is_a_warning_not_a_crash(world, monkeypatch):
    entity, runner, store = world

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(mine_record, "write", boom)
    report = bringup.bringup(entity, "stormhaven", runner=runner, do_backup=False)
    assert report.ready
    assert any("could not record mine skips: disk full" in w for w in report.warnings)
    results = refresh.refresh(entity, runner=runner)  # --all shape: no campaign given
    assert results and not any(r.failed for r in results)
    assert any("could not record mine skips" in ln for r in results for ln in r.warnings())
    monkeypatch.setattr(cli, "_load_or_exit", lambda config: entity)
    monkeypatch.setattr(MempalaceRunner, "for_entity", classmethod(lambda c, e, **k: runner))
    out = CliRunner().invoke(cli.app, ["refresh", "--all"])
    assert out.exit_code == 0 and "could not record mine skips" in out.output


def test_no_record_note_is_actionable(world):
    entity, runner, store = world
    bringup.bringup(entity, "stormhaven", runner=runner, do_backup=False)
    (store / mine_record.FILENAME).unlink()
    assert "run `mneme mp refresh stormhaven`" in _gaps(entity, runner).note


def test_restore_carries_record_over(world, monkeypatch):
    entity, runner, store = world
    monkeypatch.setenv("MNEME_STUB_MINE_SKIPS", "  SKIP: a.pdf (9.0 MB) exceeds 500 MB limit")
    bringup.bringup(entity, "stormhaven", runner=runner, do_backup=True)
    res = backup.restore(entity, "stormhaven", runner=runner, prober=lambda *a, **k: 384)
    rec = mine_record.read(store)
    assert res.previous_store is not None
    assert rec.carried_over.startswith("restore ") and "a.pdf" in rec.names
    row = _gaps(entity, runner)
    assert row.state is State.INDEX_GAPS and "(carried over by restore)" in row.note


def test_cli_regenerate_failure_still_prints_earlier_gaps(world, monkeypatch):
    """A later wing's failure must not hide gaps the earlier wings found (GH #31)."""
    entity, _runner, _ = world
    monkeypatch.setattr(cli, "_load_or_exit", lambda config: entity)
    err = MempalaceError("mempalace mine wing-b failed (rc 1)")
    err.skips = tuple(("wing-a", n) for n in parse_skips(CHUNK_NEW.format(name="bible.md")))
    err.record_warning = "WARN could not record mine skips: read-only store"

    def raiser(*a, **k):
        raise err

    monkeypatch.setattr(backup, "regenerate", raiser)
    out = CliRunner().invoke(cli.app, ["regenerate", "stormhaven", "--confirm"])
    assert out.exit_code == cli.EXIT_RUNTIME, out.output
    assert "WARN index gap: stormhaven/" in out.output and "bible.md" in out.output
    assert "WARN could not record mine skips" in out.output
    assert "FAIL regenerate:" in out.output
