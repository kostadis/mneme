"""A declared-corpus campaign wired to the recording stub (feature 007 tests).

`corpus_world(tmp_path, monkeypatch)` builds quickstart scenario 1's campaign in a real git
repo: six declared files plus decoys that must never be mined. The stub keeps its drawer
sources in a JSON state file, so a test reads back exactly what the palace holds.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from mneme.mempalace.runner import MempalaceRunner

from . import STUB, entity_for

CORPUS_YAML = """\
campaign: corp
kinds:
  npcs:
    dirs: [docs/npcs]
  summaries:
    dirs: [docs/summaries]
  grounding:
    files:
      - docs/world_state.md
      - docs/campaign_state.md
      - docs/party.md
      - docs/planning.md
    mined_as: true
  party:
    files: [docs/party.md]
"""

DECLARED = (
    "docs/npcs/a.md", "docs/summaries/001.md", "docs/world_state.md",
    "docs/campaign_state.md", "docs/party.md", "docs/planning.md",
)
DECOYS = (
    "docs/campaign_state_draft.md", "docs/party_draft.md", "docs/reviews/x.md", "summaries/raw.md",
)


@dataclass
class World:
    entity: object
    runner: MempalaceRunner
    root: Path  # campaigns tree
    camp: Path
    store: Path
    state: Path  # stub drawer-sources state
    log: Path

    def sources(self) -> list[dict]:
        return json.loads(self.state.read_text()) if self.state.exists() else []

    def source_rels(self) -> set[str]:
        root = self.camp.resolve()
        return {str(Path(r["source_file"]).relative_to(root)) for r in self.sources()}

    def wing_of(self, rel: str) -> set[str]:
        ab = str((self.camp / rel).resolve())
        return {r["wing"] for r in self.sources() if r["source_file"] == ab}

    def log_lines(self) -> list[str]:
        return self.log.read_text().splitlines() if self.log.exists() else []


def write(camp: Path, rel: str, text: str | None = None) -> None:
    p = camp / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text if text is not None else f"# {rel}\n")


def corpus_world(tmp_path, monkeypatch, *, authority: bool = True) -> World:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    state, log = tmp_path / "state.json", tmp_path / "log"
    monkeypatch.setenv("MNEME_STUB_LOG", str(log))
    monkeypatch.setenv("MNEME_STUB_SOURCES_STATE", str(state))

    def run(cmd):
        return subprocess.run([sys.executable, str(STUB), *cmd[1:]], capture_output=True, text=True)

    root = tmp_path / "campaigns"
    camp = root / "corp"
    for rel in (*DECLARED, *DECOYS):
        write(camp, rel)
    (camp / ".mneme").mkdir(exist_ok=True)
    (camp / ".mneme" / "corpus.yaml").write_text(CORPUS_YAML)
    if authority:
        (camp / ".mneme" / "mempalace.yaml").write_text(
            'campaign: corp\nrecipe_version: "3.0.0"\nstore:\n  alias: corp\n'
        )
    subprocess.run(["git", "init", "-q"], cwd=camp, check=True)  # conftest strips GIT_* vars
    mp = tmp_path / "mp"
    store = mp / "palaces" / "corp"
    return World(entity_for(root, mempalace=mp), MempalaceRunner("mempalace", run), root, camp,
                 store, state, log)


def tree_snapshot(camp: Path) -> dict[str, bytes]:
    """Every file under ``camp`` (outside .git) -> bytes, for byte-identity assertions."""
    return {
        str(p.relative_to(camp)): p.read_bytes()
        for p in sorted(camp.rglob("*")) if p.is_file() and ".git" not in p.relative_to(camp).parts
    }
