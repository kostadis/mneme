"""Invoke the `mempalace` CLI by subprocess (Principle VII/VIII — never import it).

Mirrors `mneme/lifecycle.py`: a thin, injectable runner so tests pass a fake or the
recording stub binary instead of a real palace. The binary is resolved from the
configured venv (`<venv>/bin/mempalace`) and overridable for tests.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from pathlib import Path

Runner = Callable[[list[str]], "subprocess.CompletedProcess[str]"]


class MempalaceError(Exception):
    """A `mempalace` subprocess failed."""


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True)


def _run_stream(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """Streaming runner: do NOT capture — let the child's stdout/stderr inherit our
    terminal so the user sees `mempalace mine` progress live (Principle IX, Observability).

    Force the child unbuffered (``PYTHONUNBUFFERED``) so per-file lines appear *during*
    the mine, not flushed in a lump at the end — CPython block-buffers `print()` when its
    stdout is a pipe rather than a tty (e.g. run from another tool). The returned
    stdout/stderr are empty: the output already went to the terminal, so callers that key
    an error message off the captured tail (see :meth:`MempalaceRunner.mine`) get a generic
    "see output above" note in this mode.
    """
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    proc = subprocess.run(cmd, env=env)
    return subprocess.CompletedProcess(cmd, proc.returncode, stdout="", stderr="")


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
    def for_venv(
        cls, venv: Path | None, runner: Runner | None = None, *, stream: bool = False
    ) -> MempalaceRunner:
        """Build a runner for ``<venv>/bin/mempalace``. ``stream=True`` opts into the
        non-capturing runner so subprocess progress (e.g. `mempalace mine`) is shown live
        (``-v``/``--verbose`` on the CLI); the default captures for quiet, parseable output."""
        if runner is None:
            runner = _run_stream if stream else _run
        return cls(resolve_binary(venv), runner)

    def _call(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        cmd = [self.binary, *args]
        try:
            return self.runner(cmd)
        except FileNotFoundError:
            return subprocess.CompletedProcess(cmd, 127, stdout="", stderr="mempalace not found")

    @staticmethod
    def _with_palace(palace: Path | str | None, *sub: str) -> list[str]:
        """`--palace` is a GLOBAL option — it must come BEFORE the subcommand."""
        prefix = ["--palace", str(palace)] if palace is not None else []
        return prefix + list(sub)

    def mine(self, path: Path, palace: Path | str | None = None, dry_run: bool = False) -> None:
        sub = ["mine", str(path)] + (["--dry-run"] if dry_run else [])
        out = self._call(self._with_palace(palace, *sub))
        if out.returncode != 0:
            detail = (out.stderr or out.stdout or "").strip()[-300:] or "see output above"
            raise MempalaceError(f"mempalace mine {path} failed (rc {out.returncode}): {detail}")

    def status(self, palace: Path | str | None = None) -> bool:
        """True iff `mempalace --palace <p> status` answers cleanly (the store is openable)."""
        return self._call(self._with_palace(palace, "status")).returncode == 0

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
