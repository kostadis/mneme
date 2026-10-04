"""Embedding-dimension guard (GH #26b) — fail closed before extending a palace.

A turbovec palace built with one embedder dimension cannot be extended or queried by an
embedder of another (turbovec panics on query). mneme observes the built dimension by reading
`<store>/turbovec/<collection>/store.sqlite3` `meta.dim` READ-ONLY with stdlib sqlite3 — never
importing mempalace/turbovecdb (Principles VII/VIII) — and compares it with the dimension the
embedder mempalace itself reports (see `probe_dimension`). `embedder_identity` is
deliberately NOT used: mempalace records the
wrapper function's name for every model, so it carries no information. Anything we cannot
verify is reported as unknown, never as ok (Principle I), and writes refuse on unknown.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from hypostasis.models import ConfigEntity, embedder_from_env

from .runner import MempalaceError, _merged_env, resolve_binary

PROBE_TIMEOUT = 120.0  # cold model load / first ONNX download
Prober = Callable[[ConfigEntity], "int | None"]  # entity -> mempalace's embedding dim | None
_PROBE_CODE = "from mempalace.embedding import probe_dimension; print(probe_dimension())"


class EmbedderMismatchError(MempalaceError):
    """The store's built dimension disagrees with (or cannot be verified against) the embedder."""


class GuardState(StrEnum):
    OK = "ok"
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"
    EMPTY = "empty"


@dataclass(frozen=True)
class GuardResult:
    state: GuardState
    message: str
    built: int | None = None
    expected: int | None = None

    @property
    def blocks_write(self) -> bool:
        return self.state in (GuardState.MISMATCH, GuardState.UNKNOWN)


def non_turbovec_artifacts(store_path: Path) -> list[str]:
    """Vector-store artifacts outside `turbovec/` (chroma.sqlite3, other *.sqlite3 besides the
    knowledge graph, other backend dirs). The guard cannot read these."""
    p = Path(store_path)
    if not p.is_dir():
        return []
    out = []
    for c in sorted(p.iterdir()):
        if c.name == "turbovec" or c.name == "knowledge_graph.sqlite3":
            continue
        if c.is_dir() or c.suffix == ".sqlite3":
            out.append(c.name)
    return out


def built_dimensions(store_path: Path) -> dict[str, int | None]:
    """collection -> built dim for every turbovec collection dir that holds vectors or
    anything unreadable (None = no readable store.sqlite3 / unparseable dim — NOT known-empty).
    A created-but-empty collection (readable meta, no `dim` row, `next_uid` missing or 0 —
    turbovecdb writes dim on first insert) is omitted. Never raises."""
    out: dict[str, int | None] = {}
    for d in sorted(Path(store_path).glob("turbovec/*")):
        if not d.is_dir() or not any(d.iterdir()):
            continue  # an empty collection dir holds no vectors
        dim: int | None = None
        try:
            con = sqlite3.connect(f"file:{d / 'store.sqlite3'}?mode=ro", uri=True, timeout=1.0)
            try:
                row = con.execute("SELECT value FROM meta WHERE key='dim'").fetchone()
                if row is None:
                    nu = con.execute("SELECT value FROM meta WHERE key='next_uid'").fetchone()
                    if nu is None or int(str(nu[0]).strip() or 0) == 0:
                        continue  # created but empty
            finally:
                con.close()
            if row is not None:
                dim = int(str(row[0]).strip())
                dim = dim if dim > 0 else None
        except (sqlite3.Error, ValueError, OSError):
            dim = None
        out[d.name] = dim
    return out


def built_dimension(store_path: Path) -> int | None:
    """The one built dimension, or None if no store / unknown / collections disagree."""
    known = {d for d in built_dimensions(store_path).values() if d is not None}
    return next(iter(known)) if len(known) == 1 else None


PROBE_FAILURE_TTL = 60.0  # seconds a failed probe stays cached (successes are kept)
# key -> (dim | None, failure reason, monotonic time cached)
_probe_cache: dict[str, tuple[int | None, str, float]] = {}


def effective_env(entity: ConfigEntity) -> dict[str, str]:
    """What mempalace subprocesses see: `{**os.environ, **entity.env}` (GH #46)."""
    return _merged_env(entity.env)


_probe_note = ""  # why the last real probe returned None (surfaced in guard messages)


def _mempalace_python(entity: ConfigEntity) -> str | None:
    """The interpreter of the SAME `mempalace` binary the runner executes (`resolve_binary`):
    `<venv>/bin/python` for a venv binary; else the PATH `mempalace` (resolved on the MERGED
    env's PATH) and its shebang — `#!/usr/bin/env pythonX` is resolved on that PATH, and a
    `/bin/sh` trampoline's `exec '<python>'` line is parsed. None if it can't be determined."""
    env = effective_env(entity)
    venv = entity.venv if entity.venv and str(entity.venv) != "." else None
    binary = resolve_binary(venv)
    if os.sep in binary:
        found: str | None = binary
        py = Path(binary).parent / "python"
        if py.exists():
            return str(py)
    else:
        found = shutil.which(binary, path=env.get("PATH"))
    if not found:
        return None
    try:
        lines = Path(found).read_text(errors="replace").splitlines()
    except OSError:
        return None
    if not lines or not lines[0].startswith("#!"):
        return None
    parts = lines[0][2:].split()
    if not parts:
        return None
    exe = Path(parts[0]).name
    if exe == "env" and len(parts) > 1:
        return shutil.which(parts[-1], path=env.get("PATH"))
    if exe in ("sh", "bash", "dash"):  # pip long-path trampoline
        for ln in lines[1:12]:
            m = re.match(r"""\s*'*exec'?\s+['"]([^'"]+)['"]""", ln)
            if m:
                return m.group(1)
        return None
    return parts[0]


def probe_dimension(entity: ConfigEntity) -> int | None:
    """Ask MEMPALACE for its own embedding dimension (`mempalace.embedding.probe_dimension`),
    in a subprocess with the same merged env the runner uses. mneme deliberately does NOT
    re-implement mempalace's env -> config.json -> defaults resolution or its provider URL /
    API-key handling: that would be a split-brain that drifts (GH #26). Subprocess only
    (Principle VII: never import mempalace in-process); a dedicated `mempalace` CLI verb would
    be the cleaner long-term interface. 0 / failure / garbage => None (unknown), cached per
    process (failures only for PROBE_FAILURE_TTL, keeping their reason); a TIMEOUT is not
    cached (the model may just be loading). Run from a neutral cwd so
    `python -c` can't import a stray `mempalace/` package from mneme's cwd. The cache key
    covers the interpreter and the env that changes what mempalace imports/reads (MEMPALACE_*,
    OPENAI_*, PYTHONPATH, HOME)."""
    global _probe_note
    _probe_note = ""
    python = _mempalace_python(entity)
    if python is None:
        _probe_note = "cannot locate mempalace's interpreter"
        return None
    env = effective_env(entity)
    relevant = sorted(
        (k, v)
        for k, v in env.items()
        if k.startswith(("MEMPALACE_", "OPENAI_")) or k in ("PYTHONPATH", "HOME")
    )
    key = hashlib.sha256(repr((python, relevant)).encode()).hexdigest()
    hit = _probe_cache.get(key)
    if hit is not None:
        cdim, creason, cached_at = hit
        if cdim is not None or time.monotonic() - cached_at < PROBE_FAILURE_TTL:
            _probe_note = creason  # a cached failure keeps its specific reason
            return cdim
        del _probe_cache[key]  # failure expired — the embedder may be back; re-probe
    dim: int | None
    reason = ""
    try:
        out = subprocess.run(
            [python, "-c", _PROBE_CODE],
            capture_output=True, text=True, env=env, timeout=PROBE_TIMEOUT,
            cwd=tempfile.gettempdir(),
        )
        lines = out.stdout.strip().splitlines()
        dim = int(lines[-1]) if out.returncode == 0 and lines else None
        dim = dim if dim and dim > 0 else None
        if dim is None:
            tail = (out.stderr or "").strip().splitlines()[-1:] or [""]
            reason = (
                f"embedder probe exited rc {out.returncode}"
                f"{': ' + tail[0][:160] if tail[0] else ' with no usable dimension'}"
            )
    except subprocess.TimeoutExpired:
        _probe_note = (
            f"embedder probe timed out after {PROBE_TIMEOUT:.0f}s — model may be loading; retry"
        )
        return None  # not cached
    except (subprocess.SubprocessError, OSError, ValueError) as e:
        dim = None
        reason = f"embedder probe failed: {type(e).__name__}: {str(e)[:160]}"
    _probe_note = reason
    _probe_cache[key] = (dim, reason, time.monotonic())
    return dim


default_prober: Prober = probe_dimension  # indirection so the suite can stay offline


def expected_dimension(entity: ConfigEntity, prober: Prober | None = None) -> int | None:
    """Dimension mempalace's effective embedder produces; None if it can't be determined."""
    global _probe_note
    _probe_note = ""
    return (prober or default_prober)(entity)


def _declared(entity: ConfigEntity) -> str:
    """Informational only (hypostasis `embedder` status row is where undeclared is flagged)."""
    decl = embedder_from_env(entity.env)
    return decl.describe() if decl else "not declared in hypostasis.yaml"


REBUILD = "`mneme mp regenerate <campaign> --confirm` to rebuild from scratch"


def check(
    entity: ConfigEntity, store_path: Path, prober: Prober | None = None
) -> GuardResult:
    store_path = Path(store_path)
    backend = effective_env(entity).get("MEMPALACE_BACKEND", "").strip().lower()
    foreign = non_turbovec_artifacts(store_path)
    dims = built_dimensions(store_path)
    if (backend and backend != "turbovec" and (foreign or dims)) or (foreign and not dims):
        what = f"MEMPALACE_BACKEND={backend}: " if backend and backend != "turbovec" else ""
        return GuardResult(
            GuardState.UNKNOWN,
            f"{what}store at {store_path} holds non-turbovec vectors"
            f"{' (' + ', '.join(foreign) + ')' if foreign else ''}; the guard only reads "
            f"turbovec stores, cannot verify it against the embedder",
        )
    if not dims:
        return GuardResult(GuardState.EMPTY, "no vectors yet")
    declared = _declared(entity)
    unreadable = sorted(c for c, d in dims.items() if d is None)
    known = {d for d in dims.values() if d is not None}
    if unreadable:
        return GuardResult(
            GuardState.UNKNOWN,
            f"could not read the built embedding dimension of collection(s) "
            f"{', '.join(unreadable)} in {store_path}; cannot verify against the embedder "
            f"({declared}). Inspect/restore the store (e.g. from a backup), or {REBUILD}",
            built=next(iter(known)) if len(known) == 1 else None,
        )
    if len(known) > 1:
        return GuardResult(
            GuardState.MISMATCH,
            f"store collections disagree on embedding dimension ({dims}) — incoherent store. "
            f"Embedder: {declared}. {REBUILD}",
        )
    built = next(iter(known))
    expected = expected_dimension(entity, prober)
    if expected is None:
        return GuardResult(
            GuardState.UNKNOWN,
            f"store is dim {built} but mempalace's embedder probe returned no dimension "
            f"(declared: {declared}; {_probe_note or 'embedder down?'}); cannot verify. "
            f"Fix/restore the embedder (do NOT regenerate until it answers)",
            built=built,
        )
    if built != expected:
        return GuardResult(
            GuardState.MISMATCH,
            f"embedding dimension mismatch: store built at dim {built}, mempalace's embedder "
            f"yields dim {expected} (declared: {declared}). Restore the matching embedder in "
            f"hypostasis.yaml env:, or {REBUILD}",
            built=built,
            expected=expected,
        )
    return GuardResult(
        GuardState.OK,
        f"dim {built} matches mempalace's embedder (declared: {declared})",
        built=built,
        expected=expected,
    )


def require_writable(
    entity: ConfigEntity | None, store_path: Path, prober: Prober | None = None
) -> GuardResult | None:
    """Raise EmbedderMismatchError if adding to `store_path` would be unsafe (fail closed).
    No entity ⇒ cannot know the embedder ⇒ guard skipped (returns None)."""
    if entity is None:
        return None
    result = check(entity, store_path, prober)
    if result.blocks_write:
        raise EmbedderMismatchError(result.message)
    return result


def require_embedder_answers(entity: ConfigEntity, prober: Prober | None = None) -> int:
    """Raise unless mempalace's embedder yields a dimension > 0 — called by `regenerate`
    BEFORE it deletes anything, so a down embedder never leaves the user with no store."""
    dim = expected_dimension(entity, prober)
    if dim is None:
        raise EmbedderMismatchError(
            f"mempalace's embedder probe returned no dimension (declared: {_declared(entity)}; "
            f"{_probe_note or 'embedder down?'}); "
            f"refusing to clear the store. Fix/restore the embedder first"
        )
    return dim
