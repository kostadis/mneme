"""Honest status — observed vs declared (Principle I: Silicon Truth).

`status` never echoes `hypostasis.yaml` as if it were reality. It reads the silicon:
- component drift: the source repo's HEAD vs the declared `pin` (catches the
  editable-install drift this whole project exists to kill);
- service reachability: a live probe (never "should be up");
- render drift: a rendered config's stamped source-hash vs the current authority.

Exit 0 only if EVERY check passes; 1 if any fails.

Honest limitation: for path-installed components we compare the *source tree*'s
HEAD to the pin, not the installed bytes (PEP 610 `direct_url` for a path install
records no commit). A fuller "installed == pin" check is a future enhancement.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from importlib import metadata as _md
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

from . import probe as _probe
from . import render as _render
from .models import (
    KNOWN_EMBEDDING_PROVIDERS,
    Component,
    ConfigEntity,
    Service,
    declared_embedder,
    is_editable,
)

Runner = Callable[[list[str]], "subprocess.CompletedProcess[str]"]
Prober = Callable[[Service], bool]


@dataclass(frozen=True)
class Row:
    name: str
    kind: str  # "component" | "render" | "service" | "embedder"
    observed: str
    expected: str
    ok: bool
    note: str = ""


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True)


def _git_head(path: Path, runner: Runner) -> str | None:
    result = runner(["git", "-C", str(path), "rev-parse", "HEAD"])
    return result.stdout.strip() if result.returncode == 0 else None


def _installed_version(dist: str) -> str | None:
    try:
        return _md.version(dist)
    except _md.PackageNotFoundError:
        return None


def _purelib(venv: Path, runner: Runner) -> list[Path]:
    """The ONE site-packages dir that is live for this venv (a stale dist-info from an older
    Python must not count). Ask the venv's own interpreter; fall back to the Python version
    in `pyvenv.cfg`; only if neither is available, every lib*/python*/site-packages dir."""
    py = venv / "bin" / "python"
    try:
        r = runner([str(py), "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"])
        out = Path(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None
    except OSError:
        out = None
    if out is not None and out.is_dir():
        return [out]
    cfg = venv / "pyvenv.cfg"
    if cfg.is_file():
        for line in cfg.read_text().splitlines():
            key, _, val = line.partition("=")
            if key.strip() in ("version", "version_info") and val.strip():
                mm = ".".join(val.strip().split(".")[:2])
                live = venv / "lib" / f"python{mm}" / "site-packages"
                return [live] if live.is_dir() else []
    return sorted(p for p in venv.glob("lib*/python*/site-packages") if p.is_dir())


def _url_path(url: str) -> Path | None:
    """A `file:` URL as a resolved Path (percent-decoded, symlinks resolved); else None."""
    parsed = urlparse(url)
    if parsed.scheme != "file":
        return None
    return Path(url2pathname(parsed.path)).resolve()


def installed_direct_urls(sites: list[Path]) -> list[tuple[str, str, bool]]:
    """`(dist-name, url, editable)` for every dist in `sites` carrying a PEP 610
    `direct_url.json` — read from the TARGET venv's disk, not the running interpreter."""
    found: list[tuple[str, str, bool]] = []
    for sp in sites:
        for du in sorted(sp.glob("*.dist-info/direct_url.json")):
            try:
                data = json.loads(du.read_text())
            except (OSError, ValueError):
                continue
            name = du.parent.name.removesuffix(".dist-info").rsplit("-", 1)[0]
            editable = bool((data.get("dir_info") or {}).get("editable"))
            found.append((name, str(data.get("url", "")), editable))
    return found


def _legacy_editable(sites: list[Path], target: Path) -> bool:
    """Legacy editable markers (setuptools<64 `develop`): a `*.egg-link` first line, or an
    `easy-install.pth` / `__editable__*.pth` entry, that is `target` or inside it (src-layout
    records `<repo>/src`). Other `.pth` files are not editable markers. Relative lines resolve
    against site-packages, as site.py does."""
    for sp in sites:
        pths = [*sp.glob("easy-install.pth"), *sp.glob("__editable__*.pth")]
        for f in [*sorted(sp.glob("*.egg-link")), *sorted(pths)]:
            try:
                lines = f.read_text().splitlines()
            except OSError:
                continue
            cands = lines[:1] if f.suffix == ".egg-link" else lines
            for ln in cands:
                ln = ln.strip()
                if not ln or ln.startswith(("import ", "#")):
                    continue
                found = (sp / ln).resolve()
                if found == target or target in found.parents:
                    return True
    return False


def _norm(name: str) -> str:
    return name.lower().replace("-", "_").replace(".", "_")


def install_state(venv: Path, comp: Component, runner: Runner) -> tuple[str, str]:
    """What the venv actually has for a `path` component: `(state, detail)` with state one of
    editable | editable-legacy | non-editable | elsewhere | absent.

    The dist name is NOT assumed: we match on the recorded source URL, comparing resolved
    PATHS (pip records the un-resolved abspath; a symlink, trailing slash or percent-encoding
    must not matter). A dist matching only by component name is `elsewhere`."""
    want = Path(comp.source.locator).expanduser().resolve()
    sites = _purelib(venv, runner)
    entries = installed_direct_urls(sites)
    for _name, url, editable in entries:
        if _url_path(url) == want:
            return ("editable" if editable else "non-editable", url)
    # A dist recorded as installed from elsewhere wins over legacy markers (imported first).
    for name, url, _editable in entries:
        if _norm(name) == _norm(comp.name):
            return ("elsewhere", url)
    if _legacy_editable(sites, want):
        return ("editable-legacy", "")
    return ("absent", "")


def editable_install_problem(state: tuple[str, str]) -> str | None:
    """Dev mode: None if `install_state` is an editable install from the path; else why not."""
    state, detail = state
    if state in ("editable", "editable-legacy"):
        return None
    if state == "non-editable":
        return "dev mode but installed non-editable — run `hypostasis install`"
    if state == "elsewhere":
        return f"dev mode but installed from {detail} — run `hypostasis install`"
    return "dev mode but not installed in the venv — run `hypostasis install`"


def dev_component_row(entity: ConfigEntity, comp: Component, runner: Runner) -> Row:
    """Dev-mode `path` component: observe the source tree and the INSTALLED state (Principle I).
    The pin, if any, is shown but never enforced; a non-git source is allowed (ok depends only
    on the editable-install check)."""
    src = Path(comp.source.locator).expanduser()
    head = _git_head(src, runner)
    pin_note = f"pin {comp.pin[:12]} (not enforced in dev mode)" if comp.pin else ""
    if head is None:
        observed = "editable @ (no git)"
    else:
        dirty = runner(["git", "-C", str(src), "status", "--porcelain"])
        observed = f"editable @ {head[:12]}" + (" (+dirty)" if dirty.stdout.strip() else "")
    inst = install_state(entity.venv, comp, runner)  # once: it spawns the venv interpreter
    if inst[0] == "editable-legacy":
        observed += " [legacy egg-link/.pth]"
    problem = editable_install_problem(inst)
    note = "; ".join(n for n in (problem, pin_note) if n)
    return Row(comp.name, "component", observed, "editable (dev mode)", problem is None, note)


def component_row(
    comp: Component, runner: Runner = _run, entity: ConfigEntity | None = None
) -> Row:
    """Source-HEAD-vs-pin drift for a component (the silicon truth of the pin).
    Under a dev-mode `entity`, `path` components are checked as editable instead."""
    if entity is not None and is_editable(entity, comp):
        return dev_component_row(entity, comp, runner)
    expected = comp.pin
    short = expected[:12]

    if comp.source.kind == "pypi":
        version = _installed_version(comp.source.locator)
        return Row(
            comp.name, "component", version or "(absent)", expected,
            version == expected, "" if version else "not installed",
        )

    # path / git source — pin is a git ref; compare the source tree's HEAD.
    src = Path(comp.source.locator).expanduser()
    head = _git_head(src, runner)
    version = _installed_version(comp.name)
    inst = f"installed {version}" if version else "not a pip dist (source-run)"
    if head is None:
        return Row(comp.name, "component", "?", short, False, f"source not a git repo: {src}")
    ok = head == expected
    note = inst if ok else f"{inst}; source HEAD drifted from pin"
    if entity is not None and install_state(entity.venv, comp, runner)[0].startswith("editable"):
        # Pinned mode must not bless an editable install left over from dev mode.
        return Row(comp.name, "component", head[:12], short, False,
                   "installed editable but mode is pinned — run `hypostasis install`")
    return Row(comp.name, "component", head[:12], short, ok, note)


def render_row(entity: ConfigEntity, comp: Component) -> Row:
    """Drift between a rendered config's stamped hash and the current authority."""
    target = comp.config_target
    if target is None:
        return Row(comp.name, "render", "—", "—", True, "no render target")
    if not target.exists():
        return Row(comp.name, "render", "(not rendered)", "stamped", False,
                   "config_target missing — run `hypostasis apply`")
    stamped = _render.read_stamp(target)
    current = _render.subtree_sha256(_render.component_context(entity, comp))
    ok = stamped == current
    return Row(comp.name, "render", (stamped or "?")[:12], current[:12], ok,
               "" if ok else "stale render — run `hypostasis apply`")


def service_row(name: str, service: Service, prober: Prober = _probe.reachable) -> Row:
    up = prober(service)
    note = "managed" if service.managed else "external"
    return Row(name, "service", "reachable" if up else "UNREACHABLE", "reachable", up, note)


def embedder_row(entity: ConfigEntity) -> Row | None:
    """Declared mempalace embedder (GH #26). None when mempalace isn't in play; a FAIL row
    when it is but the embedder is undeclared/incomplete (mempalace silently picks onnx)."""
    if "mempalace" not in entity.components and "MEMPALACE_BACKEND" not in entity.env:
        return None
    decl = declared_embedder(entity)
    if decl is not None and decl.known and decl.complete:
        return Row("embedder", "embedder", decl.describe(), "declared", True)
    if decl is not None and not decl.known:
        return Row(
            "embedder", "embedder", decl.describe(), "declared", False,
            f"unknown MEMPALACE_EMBEDDING_PROVIDER '{decl.provider}' — mempalace will fall "
            f"back to onnx all-MiniLM-L6-v2, 384-dim; accepted: "
            f"{', '.join(KNOWN_EMBEDDING_PROVIDERS)}",
        )
    observed = decl.describe() if decl else "(undeclared)"
    return Row(
        "embedder", "embedder", observed, "declared", False,
        "mempalace will fall back to onnx all-MiniLM-L6-v2, 384-dim — declare "
        "MEMPALACE_EMBEDDING_PROVIDER/MODEL/ENDPOINT in hypostasis.yaml env:",
    )


def status_report(
    entity: ConfigEntity, runner: Runner = _run, prober: Prober = _probe.reachable
) -> tuple[list[Row], int]:
    """All rows + exit code (0 iff every row PASS)."""
    rows: list[Row] = []
    for name in entity.order.install:
        rows.append(component_row(entity.components[name], runner, entity))
    for name in entity.order.install:
        comp = entity.components[name]
        if comp.config_template:
            rows.append(render_row(entity, comp))
    for name in entity.order.startup:
        service = entity.services.get(name)
        if service is not None:
            rows.append(service_row(name, service, prober))
    emb = embedder_row(entity)
    if emb is not None:
        rows.append(emb)
    code = 0 if all(r.ok for r in rows) else 1
    return rows, code
