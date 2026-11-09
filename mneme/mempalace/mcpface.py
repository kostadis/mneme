"""The mcp face bound to the OWNING mneme (feature 008, GH #87).

The `.mcp.json` entries are bound to the mneme that owns the campaign by ABSOLUTE paths
derived from its hypostasis config (venv + config file) -- never resolved via PATH, so a
different mneme/mempalace earlier on PATH can never be picked up by an MCP client.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

# The ONLY hypostasis-declared env keys that may reach the MCP server entry (GH #26): backend +
# embedder selection. An allow-list, never a pass-through — no *_API_KEY / secret may ever be
# written into .mcp.json. (.mcp.json is a host-local untracked face, so endpoints are fine.)
MCP_ENV_ALLOW = (
    "MEMPALACE_BACKEND",
    "MEMPALACE_EMBEDDING_PROVIDER",
    "MEMPALACE_EMBEDDING_MODEL",
    "MEMPALACE_EMBEDDING_ENDPOINT",
    "MEMPALACE_EMBEDDING_DEVICE",
)


def declared_mcp_env(env: Mapping[str, str] | None) -> dict[str, str]:
    """The allow-listed, non-empty subset of the declared env for the MCP server entry."""
    return {
        k: str(env[k]).strip() for k in MCP_ENV_ALLOW if env and str(env.get(k, "")).strip()
    }


class McpBindingError(Exception):
    """The owning mneme's programs/config cannot be located; the message lists every problem."""


class McpFaceError(Exception):
    """An existing mcp face file cannot be safely merged."""

    def __init__(self, path: Path, reason: str):
        self.path = Path(path)
        self.reason = reason
        super().__init__(f"{path}: {reason}")


@dataclass(frozen=True)
class McpBinding:
    mneme_program: Path
    mempalace_program: Path
    config_path: Path
    env: dict[str, str] = field(default_factory=dict)


def binding_for(entity, *, need_mempalace: bool) -> McpBinding:
    """Derive the absolute-path binding from a hypostasis ConfigEntity (never consults PATH).

    Programs use `.absolute()` (not `.resolve()`) so a venv `bin/` symlink is not rewritten
    to its target. Every problem is reported at once."""
    venv = Path(entity.venv).expanduser().absolute()
    mneme_program = venv / "bin" / "mneme"
    mempalace_program = venv / "bin" / "mempalace-mcp"
    problems: list[str] = []
    config_path = None
    if entity.source_path is None:
        problems.append("hypostasis config path unknown")
    else:
        config_path = Path(entity.source_path).expanduser().absolute()
        if not config_path.exists():
            problems.append(f"hypostasis config missing: {config_path}")
    if not mneme_program.exists():
        problems.append(f"mneme program missing: {mneme_program}")
    if need_mempalace and not mempalace_program.exists():
        problems.append(f"mempalace-mcp program missing: {mempalace_program}")
    if problems:
        raise McpBindingError("; ".join(problems))
    return McpBinding(
        mneme_program=mneme_program,
        mempalace_program=mempalace_program,
        config_path=config_path,
        env=declared_mcp_env(entity.env),
    )


def mneme_entry(b: McpBinding) -> dict:
    return {
        "type": "stdio",
        "command": str(b.mneme_program),
        "args": ["mp", "mcp", "--config", str(b.config_path)],
    }


def mempalace_entry(b: McpBinding, store_path) -> dict:
    return {
        "type": "stdio",
        "command": str(b.mempalace_program),
        "env": {"MEMPALACE_PALACE_PATH": str(store_path), **b.env},
    }


def _load_mergeable(path: Path) -> tuple[dict, dict]:
    """(data, mcpServers) of an existing file, or ({}, {}) when missing. Raises McpFaceError
    for exactly the shapes merge_write refuses. `null` mcpServers counts as empty."""
    data: dict = {}
    if path.exists():
        try:
            data = json.loads(path.read_text() or "{}")
        except json.JSONDecodeError as e:
            raise McpFaceError(path, f"not valid JSON ({e})") from e
        if not isinstance(data, dict):
            raise McpFaceError(path, "top level is not a JSON object")
    existing = data.get("mcpServers")
    if existing is None:
        existing = {}
    if not isinstance(existing, dict):
        raise McpFaceError(path, "`mcpServers` is not a JSON object")
    return data, existing


def check_mergeable(path: Path) -> None:
    """Raise McpFaceError iff `merge_write` would refuse `path`; no-op for a missing file."""
    path = Path(path)
    _load_mergeable(path.resolve() if path.is_symlink() else path)


def merge_write(path: Path, entries: dict[str, dict]) -> Path:
    """Merge `entries` into `path`'s `mcpServers`, preserving everything else; atomic write.

    Existing keys keep their position when replaced; new keys are appended. An unparsable or
    wrongly-shaped existing file raises McpFaceError without being modified. A symlinked
    `path` is followed: the target is replaced and the link preserved."""
    path = Path(path)
    if path.is_symlink():
        path = path.resolve()
    data, existing = _load_mergeable(path)
    data["mcpServers"] = {**existing, **entries}
    if path.exists():
        mode = stat.S_IMODE(path.stat().st_mode)
    else:
        umask = os.umask(0)
        os.umask(umask)
        mode = 0o666 & ~umask
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        os.chmod(tmp, mode)  # mkstemp is 0600; keep the file's mode across the replace
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(data, indent=2) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise
    return path


def file_reasons(
    path: Path, where: str, binding: McpBinding, store_path: Path | None
) -> list[str]:
    """Why the mcp file at `path` is not coherent with `binding` (empty => coherent).

    `where` names the file in each reason (".mcp.json", "root .mcp.json"). The mempalace
    entry is checked only when `store_path` is given (a store-less campaign has none)."""
    path = Path(path)
    if not path.is_file():
        return [f"mcp: {where} missing"]
    try:
        data = json.loads(path.read_text() or "{}")
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return [f"mcp: {where} unreadable"]
    if not isinstance(data, dict):
        return [f"mcp: {where} unreadable"]
    servers = data.get("mcpServers")
    if servers is None:
        servers = {}
    if not isinstance(servers, dict):
        return [f"mcp: {where} unreadable"]
    bad: list[str] = []
    mneme = servers.get("mneme")
    if not isinstance(mneme, dict):
        bad.append(f"mcp: {where} has no mneme server")
    else:
        if mneme.get("command") != str(binding.mneme_program):
            bad.append(f"mcp: {where} mneme command != {binding.mneme_program}")
        args = mneme.get("args")
        args = args if isinstance(args, list) else []
        want = str(binding.config_path)
        if not any(a == "--config" and b == want for a, b in zip(args, args[1:], strict=False)):
            bad.append(f"mcp: {where} mneme config != {binding.config_path}")
    if store_path is None:
        return bad
    mp = servers.get("mempalace")
    if not isinstance(mp, dict):
        bad.append(f"mcp: {where} has no mempalace server")
        return bad
    if mp.get("command") != str(binding.mempalace_program):
        bad.append(f"mcp: {where} mempalace command != {binding.mempalace_program}")
    env = mp.get("env")
    env = env if isinstance(env, dict) else {}
    if env.get("MEMPALACE_PALACE_PATH") != str(store_path):
        bad.append(f"mcp: {where} mempalace palace != store path")
    want_env = declared_mcp_env(binding.env)
    have_env = {k: str(env[k]) for k in MCP_ENV_ALLOW if env.get(k)}
    if have_env != want_env:
        keys = sorted(k for k in MCP_ENV_ALLOW if want_env.get(k) != have_env.get(k))
        bad.append(f"mcp: {where} embedder/backend env out of date ({', '.join(keys)})")
    return bad


@dataclass(frozen=True)
class CloneLayout:
    """Where a campaign sits in its clone and whether the clone root may carry the mcp entries
    (008, US4). Derived, read-only; `verdict` follows data-model.md's first-match table."""

    root: Path | None
    campaigns: tuple[str, ...]
    shared_declared: bool
    root_has_mneme_entries: bool
    verdict: str  # NO_CLONE | CONFLICT | UNDECLARED | MULTI | SINGLE
    reason: str


def _root_mneme_keys(root_mcp: Path) -> tuple[str, ...]:
    try:
        data = json.loads(root_mcp.read_text() or "{}")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ()
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    if not isinstance(servers, dict):  # includes null
        return ()
    return tuple(k for k in ("mneme", "mempalace") if k in servers)


def clone_layout(ref, entity) -> CloneLayout:
    """Classify `ref`'s clone root. Never writes."""
    tree = getattr(ref, "tree", None)
    if tree is not None:
        # `--dir` sets ref.tree to the workspace's parent, which need not be a declared tree;
        # only a DECLARED campaigns tree is ever a clone root (never write into any parent).
        roots = entity.data_roots.get("campaigns") or ()
        declared_roots = {Path(r).expanduser().resolve() for r in roots}
        if Path(tree).expanduser().resolve() not in declared_roots:
            tree = None
    if tree is None or Path(ref.path).resolve() == Path(tree).resolve():
        return CloneLayout(None, (), False, False, "NO_CLONE", "")
    root = Path(tree)
    shared_decl = entity.campaign_shared_dirs
    shared = tuple(shared_decl or ())
    try:
        children = sorted(
            p.name for p in root.iterdir()
            if not p.name.startswith(".") and p.is_dir()
        )
    except OSError:
        children = []
    campaigns = tuple(n for n in children if n not in shared)
    keys = _root_mneme_keys(root / ".mcp.json")
    declared = shared_decl is not None
    names = ", ".join(campaigns)

    def mk(verdict: str, reason: str) -> CloneLayout:
        return CloneLayout(root, campaigns, declared, bool(keys), verdict, reason)

    if declared and len(campaigns) >= 2 and keys:
        return mk(
            "CONFLICT",
            f"MISCONFIGURED: clone {root} holds {len(campaigns)} campaigns ({names}) but root "
            f".mcp.json has mneme-owned entries ({', '.join(keys)}) — nothing changed; "
            "see kostadis/campaigns#672",
        )
    if not declared:
        return mk(
            "UNDECLARED",
            "campaign_shared_dirs not declared in hypostasis.yaml — clone "
            f"{root} holds: {', '.join(children)}",
        )
    if ref.path.name in shared:
        return mk(
            "UNDECLARED",
            f"campaign '{ref.path.name}' is named in campaign_shared_dirs — a shared folder "
            f"and a campaign collide in clone {root}",
        )
    if len(campaigns) >= 2:
        return mk(
            "MULTI",
            f"clone {root} holds {len(campaigns)} campaigns ({names}) — sessions opened at "
            "the root will not have this campaign's servers",
        )
    if campaigns == (ref.path.name,):
        return mk("SINGLE", f"single-campaign clone {root}")
    return mk(
        "UNDECLARED",
        f"clone {root} does not hold campaign '{ref.path.name}' among: {names or '(none)'}",
    )
