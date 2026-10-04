"""GH #22 — `is_stale` parses the REAL `mempalace sync` report and asks the campaign's palace."""

from __future__ import annotations

import subprocess

import pytest

from mneme.mempalace.runner import MempalaceRunner

REPORT = """  === MemPalace Sync (dry run) ===
  Scanned:        10
  Kept:           5
  Gitignored:     {g}  (would remove)
  Missing:        {m}  (would remove)
  No source:      0  (kept)
  Out of scope:   {o}  (kept)
"""


def _runner(stdout="", rc=0, stderr=""):
    calls: list[list[str]] = []

    def fake(cmd):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, rc, stdout=stdout, stderr=stderr)

    return MempalaceRunner(binary="mp", runner=fake), calls


@pytest.mark.parametrize(
    ("m", "g", "stale"), [(0, 0, False), (3, 0, True), (0, 2, True), (1, 1, True)]
)
def test_counts(tmp_path, m, g, stale):
    r, _ = _runner(REPORT.format(m=m, g=g, o=0))
    chk = r.is_stale(tmp_path)
    assert chk.stale is stale and (chk.missing, chk.gitignored) == (m, g)


@pytest.mark.parametrize(
    ("stdout", "rc"),
    [
        ("", 1),
        ("No palace found at /x\n", 0),
        ("Palace dir at /x exists but has no store yet.\nRun: mempalace mine d\n", 0),
        ("DRIFT\n", 0),
    ],
)
def test_unknown(tmp_path, stdout, rc):
    r, _ = _runner(stdout, rc, stderr="boom")
    chk = r.is_stale(tmp_path)
    assert chk.stale is None and chk.reason


def test_palace_is_global_option_before_subcommand(tmp_path):
    r, calls = _runner(REPORT.format(m=0, g=0, o=0))
    r.is_stale(tmp_path, palace=tmp_path / "store")
    cmd = calls[0]
    assert cmd[cmd.index("--palace") + 1] == str(tmp_path / "store")
    assert cmd.index("--palace") < cmd.index("sync") and "--dry-run" in cmd


def test_out_of_scope_counts_as_stale(tmp_path):
    r, _ = _runner(REPORT.format(m=0, g=0, o=4))
    chk = r.is_stale(tmp_path)
    assert chk.stale is True and chk.out_of_scope == 4


def test_roots_are_repeated_after_the_dir(tmp_path):
    r, calls = _runner(REPORT.format(m=0, g=0, o=0))
    r.is_stale(tmp_path, roots=[tmp_path / "a", tmp_path / "b"])
    cmd = calls[0]
    assert cmd[cmd.index("sync") + 1] == str(tmp_path)
    assert [cmd[i + 1] for i, a in enumerate(cmd) if a == "--root"] == [
        str(tmp_path / "a"), str(tmp_path / "b")
    ]


def test_parse_failure_reason_includes_stderr(tmp_path):
    r, _ = _runner("", 0, stderr="Could not resolve palace backend")
    assert "Could not resolve palace backend" in r.is_stale(tmp_path).reason
