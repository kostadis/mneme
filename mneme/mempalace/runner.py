"""Invoke the `mempalace` CLI by subprocess (Principle VII/VIII — never import it).

Mirrors `mneme/lifecycle.py`: a thin, injectable runner so tests pass a fake or the
recording stub binary instead of a real palace. The binary is resolved from the
configured venv (`<venv>/bin/mempalace`) and overridable for tests.
"""

from __future__ import annotations

import functools
import os
import re
import subprocess
import sys
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .mine_report import SkipNotice, parse_skips

if TYPE_CHECKING:
    from hypostasis.config import ConfigEntity

Runner = Callable[[list[str]], "subprocess.CompletedProcess[str]"]


_GITIGNORED_RE = re.compile(r"^\s*Gitignored:\s+(\d+)", re.MULTILINE)
_MISSING_RE = re.compile(r"^\s*Missing:\s+(\d+)", re.MULTILINE)
_OUT_OF_SCOPE_RE = re.compile(r"^\s*Out of scope:\s+(\d+)", re.MULTILINE)


@dataclass(frozen=True)
class SyncCheck:
    """Result of `is_stale` (GH #22). `stale` is None when it could not be determined."""

    stale: bool | None
    missing: int
    gitignored: int
    out_of_scope: int = 0
    reason: str = ""


@dataclass(frozen=True)
class MineResult:
    """What a successful `mempalace mine` reported as skipped (GH #31). Callers may ignore it."""

    skips: tuple[SkipNotice, ...] = ()


class MempalaceError(Exception):
    """A `mempalace` subprocess failed."""


def _merged_env(env: Mapping[str, str] | None) -> dict[str, str]:
    """Ambient environment with the declared overlay winning (GH #46 — Principle V)."""
    return {**os.environ, **(env or {})}


def _run(
    cmd: list[str], env: Mapping[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Capturing runner. ``env`` (hypostasis ``env:``) is overlaid on ``os.environ``."""
    return subprocess.run(cmd, capture_output=True, text=True, env=_merged_env(env))


def _tee(src, sink_name: str, collected: list[str]) -> None:
    """Forward each line to the CURRENT ``sys.<sink_name>`` as it arrives, and keep it.

    Must NEVER stop draining: a dead reader fills the pipe and blocks the child forever.
    Any failure is recorded in ``collected`` and the rest is drained in binary."""
    try:
        for line in iter(src.readline, ""):
            collected.append(line)
            sink = getattr(sys, sink_name)
            try:
                sink.write(line)
                sink.flush()
            except (OSError, ValueError):  # a closed terminal must not kill the mine
                pass
    except Exception as e:  # noqa: BLE001 - keep draining, whatever happened
        collected.append(f"\n[mneme: output reader error: {e!r}]\n")
        try:
            while src.buffer.read(65536):
                pass
        except Exception:  # noqa: BLE001, S110
            pass


def _run_stream(
    cmd: list[str], env: Mapping[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Tee runner (GH #31): show `mempalace mine` progress live (Principle IX) AND capture it,
    so skipped files can be named even under ``-v``.

    The child's stdout/stderr are pipes; one reader thread per stream forwards each line to
    our own stdout/stderr as it arrives (flushed) and collects it. ``PYTHONUNBUFFERED`` keeps
    the child from block-buffering `print()` into a lump at the end (it is not on a tty).
    Returns the collected stdout/stderr, so error tails are real, not "see output above".
    """
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",  # undecodable bytes must not kill a reader (and hang the child)
        env={**_merged_env(env), "PYTHONUNBUFFERED": "1"},
    )
    out: list[str] = []
    err: list[str] = []
    threads = [
        threading.Thread(target=_tee, args=(proc.stdout, "stdout", out), daemon=True),
        threading.Thread(target=_tee, args=(proc.stderr, "stderr", err), daemon=True),
    ]
    for t in threads:
        t.start()
    rc = proc.wait()
    for t in threads:
        t.join()
    return subprocess.CompletedProcess(cmd, rc, stdout="".join(out), stderr="".join(err))


def resolve_binary(venv: Path | None) -> str:
    """`<venv>/bin/mempalace` if a venv is given, else bare `mempalace` (PATH)."""
    if venv is not None:
        candidate = Path(venv).expanduser() / "bin" / "mempalace"
        if candidate.exists():
            return str(candidate)
    return "mempalace"


class MempalaceRunner:
    def __init__(
        self,
        binary: str = "mempalace",
        runner: Runner = _run,
        env: Mapping[str, str] | None = None,
    ):
        self.binary = binary
        self.runner = runner
        # The hypostasis-declared overlay (e.g. MEMPALACE_BACKEND), exposed for assertions.
        self.env: dict[str, str] = dict(env or {})

    @classmethod
    def for_venv(
        cls,
        venv: Path | None,
        runner: Runner | None = None,
        *,
        stream: bool = False,
        env: Mapping[str, str] | None = None,
    ) -> MempalaceRunner:
        """Build a runner for ``<venv>/bin/mempalace``. ``stream=True`` opts into the
        non-capturing runner so subprocess progress (e.g. `mempalace mine`) is shown live
        (``-v``/``--verbose`` on the CLI); the default captures for quiet, parseable output.

        ``env`` is the hypostasis-declared overlay, merged over ``os.environ`` for every
        subprocess the DEFAULT runners launch (GH #46). An injected ``runner`` is called with
        just ``cmd`` and owns its own environment."""
        if runner is None:
            base = _run_stream if stream else _run
            runner = functools.partial(base, env=dict(env or {}))
        return cls(resolve_binary(venv), runner, env)

    @classmethod
    def for_entity(
        cls, entity: ConfigEntity, runner: Runner | None = None, *, stream: bool = False
    ) -> MempalaceRunner:
        """Runner for the entity's venv carrying ``entity.env`` (GH #46 — Principle V), so
        `mempalace` sees the declared backend rather than whatever the shell has set."""
        venv = entity.venv if entity.venv and str(entity.venv) != "." else None
        return cls.for_venv(venv, runner, stream=stream, env=entity.env)

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

    def mine(self, path: Path, palace: Path | str | None = None, dry_run: bool = False
    ) -> MineResult:
        """Mine ``path``; raise on failure. On success returns the skips parsed from the
        combined stdout + stderr (GH #31 — a skipped file is a named gap, never silent)."""
        sub = ["mine", str(path)] + (["--dry-run"] if dry_run else [])
        out = self._call(self._with_palace(palace, *sub))
        if out.returncode != 0:
            detail = (out.stderr or out.stdout or "").strip()[-300:] or "no output"
            raise MempalaceError(f"mempalace mine {path} failed (rc {out.returncode}): {detail}")
        return MineResult(tuple(parse_skips(f"{out.stdout or ''}\n{out.stderr or ''}")))

    def status(self, palace: Path | str | None = None) -> bool:
        """True iff `mempalace --palace <p> status` answers cleanly (the store is openable)."""
        return self._call(self._with_palace(palace, "status")).returncode == 0

    def is_stale(
        self,
        path: Path,
        palace: Path | str | None = None,
        roots: Sequence[Path | str] = (),
    ) -> SyncCheck:
        """Orphaned-index check via `mempalace [--palace P] sync <path> --dry-run` (GH #22).

        Detects ORPHANED index entries only: drawers whose source is now gitignored or
        missing. It does NOT detect new or changed sources — mempalace has no CLI for that
        (`mine --dry-run` skips the already-mined check). Anything we cannot parse is
        `stale=None` (unknown), never a guess (Principle I). Pass `palace` so the campaign's
        own store is asked, not whatever default resolves. `roots` are the other legitimate
        source roots (multi-root wings); drawers outside every root are `out_of_scope`
        (a moved campaign or a foreign store) and count as stale.
        """
        root_args = [a for r in roots for a in ("--root", str(r))]
        out = self._call(self._with_palace(palace, "sync", str(path), *root_args, "--dry-run"))
        if out.returncode != 0:
            detail = (out.stderr or out.stdout or "").strip()[-200:]
            return SyncCheck(None, 0, 0, 0, f"sync failed (rc {out.returncode}): {detail}")
        text = out.stdout or ""
        gi = _GITIGNORED_RE.search(text)
        ms = _MISSING_RE.search(text)
        if gi is None or ms is None:
            first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "no output")
            err = (out.stderr or "").strip()[-200:]
            tail = f"; stderr: {err}" if err else ""
            return SyncCheck(None, 0, 0, 0, f"no sync report ({first[:120]}){tail}")
        g, m = int(gi.group(1)), int(ms.group(1))
        oo = _OUT_OF_SCOPE_RE.search(text)
        o = int(oo.group(1)) if oo else 0
        return SyncCheck(g + m + o > 0, m, g, o, "")

    def split(self, path: Path, *extra: str) -> None:
        out = self._call(["split", str(path), *extra])
        if out.returncode != 0:
            detail = (out.stderr or out.stdout or "").strip()[-300:]
            raise MempalaceError(f"mempalace split {path} failed (rc {out.returncode}): {detail}")
