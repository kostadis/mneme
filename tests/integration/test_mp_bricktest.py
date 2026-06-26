"""Polish (T041) — the Brick Test: FR-011 / SC-005 / Principle IV.

Wiping mneme's local state must lose no per-campaign config: the authority and the
recorded dispositions live in the campaign, and the manager reconstructs the full
view from the campaigns alone. mneme keeps no index metadata or per-campaign store of
its own, so the report is reproducible after discarding everything mneme-local."""

from __future__ import annotations

import shutil
import subprocess

from mneme.mempalace import authority, conform, workcopy
from mneme.mempalace.runner import MempalaceRunner
from tests.fixtures import entity_for, make_campaigns


def _clean_runner():
    def run(cmd):
        out = "CLEAN" if cmd[1] == "sync" else ""
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

    return MempalaceRunner(binary="mempalace", runner=run)


def _fingerprint(report):
    return sorted((r.campaign, r.dimension, r.state.value, r.note) for r in report.rows)


def test_management_view_survives_wiping_mneme_local_state(tmp_path, monkeypatch):
    root = make_campaigns(tmp_path / "campaigns")
    entity = entity_for(root)

    before = _fingerprint(conform.report(entity, runner=_clean_runner()))
    disp_before = authority.load(root / "full").dispositions

    # Wipe everything mneme-local: its XDG state dir / private working copy.
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    state = workcopy.default_state_dir()
    state.mkdir(parents=True, exist_ok=True)
    (state / "stray.txt").write_text("mneme scratch")
    shutil.rmtree(state)  # discard the manager's only local artifact

    # Re-derive the view from the campaigns alone — identical, zero re-entry.
    after = _fingerprint(conform.report(entity, runner=_clean_runner()))
    assert after == before

    # The authority + dispositions survived because they live in the campaign.
    disp_after = authority.load(root / "full").dispositions
    assert disp_after == disp_before
    assert disp_after[0].kind == "deliberate"  # the recorded "why" is intact
