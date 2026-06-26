"""Invoke the `mempalace` CLI by subprocess (Principle VII/VIII — never import it).

Mirrors `mneme/lifecycle.py`: a thin, injectable runner so tests pass a fake or the
recording stub binary instead of a real palace. The binary is resolved from the
configured venv (`<venv>/bin/mempalace`) and overridable for tests.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

Runner = Callable[[list[str]], "subprocess.CompletedProcess[str]"]


class MempalaceError(Exception):
    """A `mempalace` subprocess failed."""


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True)


def resolve_binary(venv: Path | None) -> str:
    """`<venv>/bin/mempalace` if a venv is given, else bare `mempalace` (PATH)."""
    if venv is not None:
        candidate = Path(venv).expanduser() / "bin" / "mempalace"
        if candidate.exists():
            return str(candidate)
    return "mempalace"


class MempalaceRunner:
    def __init__(self, binary: str = "mempalace", runner: Runner = _run):
        self.binary = binary
        self.runner = runner

    @classmethod
    def for_venv(cls, venv: Path | None, runner: Runner = _run) -> MempalaceRunner:
        return cls(resolve_binary(venv), runner)

    def _call(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        cmd = [self.binary, *args]
        try:
            return self.runner(cmd)
        except FileNotFoundError:
            return subprocess.CompletedProcess(cmd, 127, stdout="", stderr="mempalace not found")

    def mine(self, path: Path, palace: Path | str | None = None, dry_run: bool = False) -> None:
        args = ["mine", str(path)]
        if palace is not None:
            args += ["--palace", str(palace)]
        if dry_run:
            args += ["--dry-run"]
        out = self._call(args)
        if out.returncode != 0:
            detail = (out.stderr or out.stdout or "").strip()[-300:]
            raise MempalaceError(f"mempalace mine {path} failed (rc {out.returncode}): {detail}")

    def status(self, palace: Path | str | None = None) -> bool:
        """True iff `mempalace status --palace <p>` answers cleanly (the store is openable)."""
        args = ["status"] + (["--palace", str(palace)] if palace is not None else [])
        return self._call(args).returncode == 0

    def is_stale(self, path: Path) -> bool:
        """Source-vs-index drift via `mempalace sync --dry-run` (D2). True ⇒ stale.

        mneme stores no index metadata of its own; staleness is asked of mempalace
        (Principle III/IV). A non-zero/unparseable result is treated as unknown→False.
        """
        out = self._call(["sync", str(path), "--dry-run"])
        if out.returncode != 0:
            return False
        return "DRIFT" in (out.stdout or "").upper()

    def split(self, path: Path, *extra: str) -> None:
        out = self._call(["split", str(path), *extra])
        if out.returncode != 0:
            detail = (out.stderr or out.stdout or "").strip()[-300:]
            raise MempalaceError(f"mempalace split {path} failed (rc {out.returncode}): {detail}")
