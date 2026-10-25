"""Invoke the `mempalace` CLI by subprocess (Principle VII/VIII — never import it).

Mirrors `mneme/lifecycle.py`: a thin, injectable runner so tests pass a fake or the
recording stub binary instead of a real palace. The binary is resolved from the
configured venv (`<venv>/bin/mempalace`) and overridable for tests.
"""

from __future__ import annotations

import functools
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from mneme import atomic as _atomic

from .mine_report import SkipNotice, parse_skips

if TYPE_CHECKING:
    from hypostasis.config import ConfigEntity

Runner = Callable[[list[str]], "subprocess.CompletedProcess[str]"]


_GITIGNORED_RE = re.compile(r"^\s*Gitignored:\s+(\d+)", re.MULTILINE)
_MISSING_RE = re.compile(r"^\s*Missing:\s+(\d+)", re.MULTILINE)
_OUT_OF_SCOPE_RE = re.compile(r"^\s*Out of scope:\s+(\d+)", re.MULTILINE)


def _top_sources(text: str) -> tuple[str, ...]:
    """The indented lines under `Top sources to remove|removed:` (up to the next blank line)."""
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if ln.strip().startswith("Top sources"):
            found: list[str] = []
            for nxt in lines[i + 1:]:
                if not nxt.strip():
                    break
                found.append(nxt.strip())
            return tuple(found)
    return ()


@dataclass(frozen=True)
class SyncCheck:
    """Result of `is_stale` (GH #22). `stale` is None when it could not be determined."""

    stale: bool | None
    missing: int
    gitignored: int
    out_of_scope: int = 0
    reason: str = ""
    top_sources: tuple[str, ...] = ()  # "path  (n)" lines from the report's top-sources list


@dataclass(frozen=True)
class MineResult:
    """What a successful `mempalace mine` reported as skipped (GH #31). Callers may ignore it."""

    skips: tuple[SkipNotice, ...] = ()


@dataclass(frozen=True)
class ListedSkip:
    """One listed file mempalace did not (fully) mine, from `mine --skips-json` (GM 2026-10-24).
    ``path`` is as listed, relative to the mine dir (POSIX); ``reason`` is mempalace's code
    (missing, symlink, too_large, chunk_cap, ...) — an unknown code is still a skip."""

    path: str
    reason: str
    detail: str = ""


@dataclass(frozen=True)
class SourceRecord:
    """One distinct `(wing, source_file)` in the store (`mempalace sources --json`, 007 R3)."""

    wing: str
    source_file: str  # absolute, as mempalace stored it
    source_mtime: float | None
    drawers: int


@dataclass(frozen=True)
class ForgetReport:
    """The parsed `mempalace forget` report: sources and drawers to delete (or deleted)."""

    sources: int
    drawers: int
    paths: tuple[str, ...] = ()  # the "<path>" of each `  <path>  (<count>)` line


_FORGET_SOURCES_RE = re.compile(r"^\s*Sources:\s+(\d+)", re.MULTILINE)
_FORGET_DRAWERS_RE = re.compile(r"^\s*Drawers:\s+(\d+)", re.MULTILINE)
_FORGET_LINE_RE = re.compile(r"^\s+(\S.*?)\s+\((\d+)\)\s*$", re.MULTILINE)
_CORPUS_VERBS = ("sources", "forget")
_MINE_FLAGS = ("--files-from", "--skips-json")


CANNOT_RUN = "cannot run mempalace"


class MempalaceError(Exception):
    """A `mempalace` subprocess failed."""


def _read_skips(path: Path) -> list[ListedSkip] | None:
    """The `--skips-json` array, or None when it is absent or not a list of {path, reason}."""
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            return None
        return [ListedSkip(str(r["path"]), str(r["reason"]), str(r.get("detail") or ""))
                for r in rows]
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return None


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


def _is_sidecar(name: str) -> bool:
    """mneme's own record (`mneme-*.json`), or the temp file `atomic.write_json` leaves when a
    write was interrupted (`.mneme-*.json.<rand>.tmp`)."""
    if name.startswith("mneme-") and name.endswith(".json"):
        return True
    return name.startswith(".mneme-") and _atomic.is_temp(name)


class StoreKind(Enum):
    MISSING = "missing"  # nothing there (and not a symlink)
    EMPTY = "empty"  # a directory holding only mneme sidecars / write_json temps
    BROKEN = "broken"  # exists but is not a directory, or a dangling symlink
    PRESENT = "present"  # a directory with palace content


@dataclass(frozen=True)
class StoreClass:
    kind: StoreKind
    reason: str | None = None  # set iff BROKEN

    @property
    def unprovisioned(self) -> bool:
        """No palace there yet: MISSING or EMPTY."""
        return self.kind in (StoreKind.MISSING, StoreKind.EMPTY)


# What every refusal of a BROKEN store path starts with (callers that must not suggest bringup).
BROKEN_STORE = "store path is "


def store_state(store: Path) -> StoreClass:
    """The ONE classification of a store path. A non-directory that exists, or a dangling
    symlink, is BROKEN — never "not provisioned" (bringup refuses it too)."""
    store = Path(store)
    if store.is_symlink() and not store.exists():
        return StoreClass(StoreKind.BROKEN, f"{BROKEN_STORE}a dangling symlink: {store}")
    if not store.exists():
        return StoreClass(StoreKind.MISSING)
    if not store.is_dir():
        return StoreClass(StoreKind.BROKEN, f"{BROKEN_STORE}not a directory: {store}")
    try:
        empty = all(_is_sidecar(p.name) for p in store.iterdir())
    except OSError:
        return StoreClass(StoreKind.PRESENT)
    return StoreClass(StoreKind.EMPTY if empty else StoreKind.PRESENT)


@dataclass(frozen=True)
class SourcesResult:
    """`sources` read: ``rows`` is None when unknown; ``error`` says why when the binary could
    not be launched (else None — rc != 0 / unparseable output carry no launch error)."""

    rows: list[SourceRecord] | None
    error: str | None = None

    def why(self) -> str:
        """The one message for an unreadable `sources`."""
        return self.error or "`mempalace sources` failed or returned unparseable output"


@dataclass(frozen=True)
class StatusResult:
    ok: bool
    error: str | None = None


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
        self._read_gaps: list[str] | None = None
        self._mine_gaps: list[str] | None = None

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

    def _call_checked(
        self, args: list[str]
    ) -> tuple[subprocess.CompletedProcess[str], str | None]:
        """Run one subcommand. A binary that cannot be launched (missing, not executable, ...)
        is ONE shape: rc 127 with ``stderr`` = "cannot run mempalace: <why>", also returned as
        the second element (else None)."""
        cmd = [self.binary, *args]
        try:
            return self.runner(cmd), None
        except OSError as e:
            err = f"{CANNOT_RUN}: {e}"
            return subprocess.CompletedProcess(cmd, 127, stdout="", stderr=err), err

    def _call(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        return self._call_checked(args)[0]

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

    def mine_files(
        self,
        root: Path,
        files: Sequence[Path | str],
        wing: str,
        palace: Path | str | None = None,
        dry_run: bool = False,
    ) -> list[ListedSkip] | None:
        """Mine exactly ``files`` under ``root`` into ``wing`` (`mine --files-from`, 007 R1).
        Pass resolved targets, never symlinks. Raises on failure. Returns the listed files
        mempalace did not mine, read from `--skips-json` — never from its text output; None
        when that file is missing or unparseable after the run (unknown, not "no skips")."""
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write("".join(f"{f}\n" for f in files))
        skips_out = Path(fh.name).with_suffix(".skips.json")
        try:
            sub = ["mine", str(root), "--files-from", fh.name, "--wing", wing,
                   "--skips-json", str(skips_out)]
            if dry_run:
                sub.append("--dry-run")
            out = self._call(self._with_palace(palace, *sub))
            skips = _read_skips(skips_out)
        finally:
            Path(fh.name).unlink(missing_ok=True)
            skips_out.unlink(missing_ok=True)
        if out.returncode != 0:
            detail = (out.stderr or out.stdout or "").strip()[-300:] or "no output"
            raise MempalaceError(
                f"mempalace mine --files-from {root} failed (rc {out.returncode}): {detail}"
            )
        return skips

    def sources(
        self, palace: Path | str | None = None, wing: str | None = None
    ) -> list[SourceRecord] | None:
        """`read_sources(...).rows`: every `(wing, source_file)` in the store, or None."""
        return self.read_sources(palace, wing).rows

    def read_sources(
        self, palace: Path | str | None = None, wing: str | None = None
    ) -> SourcesResult:
        """Every `(wing, source_file)` in the store, or ``rows=None`` when it cannot be read:
        rc != 0 or unparseable output is unknown, never an empty list (FR-017, 007 R3). Never
        raises; when the binary cannot be launched, ``error`` says why."""
        sub = ["sources", "--json"] + (["--wing", wing] if wing else [])
        out, err = self._call_checked(self._with_palace(palace, *sub))
        if out.returncode != 0:
            return SourcesResult(None, err)
        try:
            rows = json.loads(out.stdout or "")
            return SourcesResult([
                SourceRecord(
                    str(r["wing"]),
                    str(r["source_file"]),
                    None if r.get("source_mtime") is None else float(r["source_mtime"]),
                    int(r["drawers"]),
                )
                for r in rows
            ])
        except (ValueError, TypeError, KeyError):
            return SourcesResult(None)

    def forget(
        self,
        sources: Sequence[Path | str],
        palace: Path | str | None = None,
        apply: bool = False,
        wing: str | None = None,
    ) -> ForgetReport:
        """`forget --sources-from F [--wing W] [--apply]` (007 R4). Dry run by default; a failed
        or unparseable run raises `MempalaceError` so a caller never assumes it worked."""
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write("".join(f"{s}\n" for s in sources))
        try:
            sub = ["forget", "--sources-from", fh.name]
            if wing:
                sub += ["--wing", wing]
            if apply:
                sub.append("--apply")
            out = self._call(self._with_palace(palace, *sub))
        finally:
            Path(fh.name).unlink(missing_ok=True)
        if out.returncode != 0:
            detail = (out.stderr or out.stdout or "").strip()[-300:] or "no output"
            raise MempalaceError(f"mempalace forget failed (rc {out.returncode}): {detail}")
        text = out.stdout or ""
        ns, nd = _FORGET_SOURCES_RE.search(text), _FORGET_DRAWERS_RE.search(text)
        if ns is None or nd is None:
            first = text.strip()[:120] or "no output"
            raise MempalaceError(f"mempalace forget: no report ({first})")
        paths = tuple(m.group(1) for m in _FORGET_LINE_RE.finditer(text))
        return ForgetReport(int(ns.group(1)), int(nd.group(1)), paths)

    def _help(self, args: list[str]) -> str:
        """`mempalace <args> --help` stdout. A probe that cannot run (crash, broken venv,
        missing binary) raises: that is not "too old", and nothing is cached from it."""
        out = self._call([*args, "--help"])
        if out.returncode != 0:
            detail = (out.stderr or out.stdout or "").strip()[-200:] or "no output"
            raise MempalaceError(
                f"cannot probe mempalace capabilities: `{' '.join([*args, '--help'])}` "
                f"failed (rc {out.returncode}): {detail}"
            )
        return out.stdout or ""

    def read_gaps(self) -> list[str]:
        """What this mempalace lacks to READ and FORGET a corpus: the `sources` / `forget`
        verbs. Empty = supported. Probed once per runner (a failed probe raises, uncached)."""
        if self._read_gaps is None:
            top = self._help([])
            self._read_gaps = [f"`{v}`" for v in _CORPUS_VERBS if v not in top]
        return self._read_gaps

    def mine_gaps(self) -> list[str]:
        """What this mempalace lacks to MINE a corpus: `mine --files-from` / `--skips-json`."""
        if self._mine_gaps is None:
            mine = self._help(["mine"])
            self._mine_gaps = [f"`mine {f}`" for f in _MINE_FLAGS if f not in mine]
        return self._mine_gaps

    def corpus_gaps(self) -> list[str]:
        """Everything the full mining capability lacks, named (read gaps first). Empty =
        supported."""
        return [*self.read_gaps(), *self.mine_gaps()]

    def supports_corpus_read(self) -> bool:
        """`sources` + `forget` only: enough for status, prune and corpus reads (they never
        mine)."""
        return not self.read_gaps()

    def supports_corpus(self) -> bool:
        """The full mining capability (007 Dependency 1; `--skips-json`, GM 2026-10-24):
        `corpus_gaps()` is empty. Refresh / bringup / regenerate need this."""
        return not self.corpus_gaps()

    def too_old_message(self) -> str:
        """The refusal for a mempalace that cannot mine a corpus, naming what is missing."""
        return f"mempalace too old for corpus mining (missing {', '.join(self.corpus_gaps())})"

    def read_too_old_message(self) -> str:
        """The refusal for a mempalace that cannot read or forget a corpus."""
        return f"this mempalace lacks corpus support (missing {', '.join(self.read_gaps())})"

    def search(
        self,
        query: str,
        palace: Path | str | None = None,
        *,
        wing: str | None = None,
        room: str | None = None,
        results: int | None = None,
        since: str | None = None,
        before: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """`mempalace [--palace P] search QUERY [--wing W] [--room R] [--results N] [--since D]
        [--before D] -- QUERY` (GH #73; `--` keeps a query starting with '-' from being read as
        an option). Read-only; absent filters are omitted. Returns the process so the caller
        propagates failure (a stream runner has already shown the output)."""
        flags = [
            a
            for flag, val in (
                ("--wing", wing), ("--room", room), ("--results", results),
                ("--since", since), ("--before", before),
            )
            if val is not None
            for a in (flag, str(val))
        ]
        return self._call(self._with_palace(palace, "search", *flags, "--", query))

    def status(self, palace: Path | str | None = None) -> bool:
        """True iff `mempalace --palace <p> status` answers cleanly (the store is openable)."""
        return self.probe_status(palace).ok

    def probe_status(self, palace: Path | str | None = None) -> StatusResult:
        """`status`, carrying why the binary could not be launched (else ``error`` is None)."""
        out, err = self._call_checked(self._with_palace(palace, "status"))
        return StatusResult(out.returncode == 0, err)

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
        return self.sync(path, palace, roots, apply=False)

    def sync(
        self,
        path: Path,
        palace: Path | str | None = None,
        roots: Sequence[Path | str] = (),
        apply: bool = False,
    ) -> SyncCheck:
        """`mempalace [--palace P] sync <path> [--root R ...] (--dry-run | --apply)`.

        Dry-run never raises (unknown is `stale=None`, Principle I). `apply` DELETES the
        drawers whose source is missing or gitignored (out-of-scope are kept) — deletion is
        an explicit, reviewed step (`mneme mp prune`); a failed or unparseable apply raises
        `MempalaceError` so a caller never assumes it worked.
        """
        root_args = [a for r in roots for a in ("--root", str(r))]
        mode = "--apply" if apply else "--dry-run"
        out = self._call(self._with_palace(palace, "sync", str(path), *root_args, mode))
        if out.returncode != 0:
            detail = (out.stderr or out.stdout or "").strip()[-200:]
            if apply:
                raise MempalaceError(
                    f"mempalace sync --apply {path} failed (rc {out.returncode}): {detail}"
                )
            return SyncCheck(None, 0, 0, 0, f"sync failed (rc {out.returncode}): {detail}")
        text = out.stdout or ""
        gi = _GITIGNORED_RE.search(text)
        ms = _MISSING_RE.search(text)
        if gi is None or ms is None:
            first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "no output")
            err = (out.stderr or "").strip()[-200:]
            tail = f"; stderr: {err}" if err else ""
            reason = f"no sync report ({first[:120]}){tail}"
            if apply:
                raise MempalaceError(f"mempalace sync --apply {path}: {reason}")
            return SyncCheck(None, 0, 0, 0, reason)
        g, m = int(gi.group(1)), int(ms.group(1))
        oo = _OUT_OF_SCOPE_RE.search(text)
        o = int(oo.group(1)) if oo else 0
        return SyncCheck(g + m + o > 0, m, g, o, "", _top_sources(text))

    def split(self, path: Path, *extra: str) -> None:
        out = self._call(["split", str(path), *extra])
        if out.returncode != 0:
            detail = (out.stderr or out.stdout or "").strip()[-300:]
            raise MempalaceError(f"mempalace split {path} failed (rc {out.returncode}): {detail}")
