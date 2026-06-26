"""Per-campaign lifecycle — bring CampaignGenerator up for one campaign.

`mneme` runs ON the environment `hypostasis` configured. `up`:
1. resolve the campaign workspace (data_roots.campaigns / <campaign>);
2. health-gate the shared substrate (the external deps — DGX, rpg-lib — must be up,
   that's the substrate's job; never assume — Principle I);
3. refresh CG's wiring (the shared external config);
4. export the hypostasis `env:` (e.g. MEMPALACE_BACKEND) into CG's process;
5. start CG scoped to the campaign on its own port (CG's `start` script).
`down` stops that instance via CG's `stop`.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from hypostasis import probe as _probe
from hypostasis import render as _render
from hypostasis.models import ConfigEntity, Service

Runner = Callable[[list[str], dict], "subprocess.CompletedProcess[str]"]
Prober = Callable[[Service], bool]


class LifecycleError(Exception):
    """A per-campaign up/down failure. CLI maps to exit 1."""


def _run(cmd: list[str], env: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, env=env, capture_output=True, text=True)


def _campaign_dir(entity: ConfigEntity, campaign: str, override: str | None = None) -> Path:
    """Resolve the campaign workspace: an explicit ``override`` path wins; otherwise
    the campaign NAME is resolved against ``data_roots.campaigns`` (config-based)."""
    if override:
        cdir = Path(override).expanduser()
        if not cdir.is_dir():
            raise LifecycleError(f"campaign workspace not found: {cdir}")
        return cdir
    root = entity.data_roots.get("campaigns")
    if root is None:
        raise LifecycleError("hypostasis.yaml has no data_roots.campaigns (or pass --dir)")
    cdir = Path(root) / campaign
    if not cdir.is_dir():
        raise LifecycleError(f"campaign workspace not found: {cdir} (or pass --dir)")
    return cdir


def _cg_source(entity: ConfigEntity) -> Path:
    comp = entity.components.get("CampaignGenerator")
    if comp is None:
        raise LifecycleError("hypostasis.yaml has no CampaignGenerator component")
    return Path(comp.source.locator).expanduser()


def unreachable_deps(entity: ConfigEntity, prober: Prober = _probe.reachable) -> list[str]:
    """External (managed: false) deps in startup order that are NOT reachable."""
    return [
        n for n in entity.order.startup
        if (s := entity.services.get(n)) is not None and not s.managed and not prober(s)
    ]


def mempalace_not_ready(cdir: Path) -> str | None:
    """`mneme up` store-health gate (003, FR-010). Returns None if the campaign's mempalace
    store is brought up and healthy — OR if the campaign declares no store pointer yet (a
    pre-003 campaign is not gated). Otherwise a reason string. mneme up FAILS on a reason;
    it never brings the store up itself."""
    from .mempalace import authority as _a
    from .mempalace import health as _h

    if not _a.has_authority(cdir):
        return None  # not a 003-managed campaign — nothing to gate
    try:
        cfg = _a.load(cdir)
    except _a.AuthorityError:
        return None
    if cfg.store is None:
        return None
    sh = _h.health(cfg.store.path)
    return None if sh.ok else sh.note


@dataclass
class UpResult:
    campaign: str
    port: int
    campaign_dir: str
    command: list[str]
    env_exported: list[str]
    deps_ok: list[str]
    dry_run: bool
    rc: int | None = None

    def report(self) -> list[str]:
        lines = [
            f"campaign : {self.campaign}  (dir {self.campaign_dir})",
            f"deps ok  : {', '.join(self.deps_ok) or '(none)'}",
            f"env      : {', '.join(self.env_exported) or '(none)'}",
            f"start    : {' '.join(self.command)}",
        ]
        if self.dry_run:
            lines.append("DRY-RUN: not started")
        elif self.rc == 0:
            lines.append(f"OK: CampaignGenerator up for '{self.campaign}' on port {self.port}")
        return lines


def up(
    entity: ConfigEntity,
    campaign: str,
    *,
    campaign_dir: str | None = None,
    session: str | None = None,
    port: int = 5000,
    prober: Prober = _probe.reachable,
    runner: Runner = _run,
    render: bool = True,
    dry_run: bool = False,
    store_gate: Callable[[Path], str | None] = mempalace_not_ready,
) -> UpResult:
    cdir = _campaign_dir(entity, campaign, campaign_dir)
    deps = [n for n in entity.order.startup if entity.services.get(n) is not None]
    cmd = [str(_cg_source(entity) / "start"), "--campaign-dir", str(cdir), "--port", str(port)]
    if session:
        cmd += ["--session-dir", session]
    result = UpResult(campaign, port, str(cdir), cmd, sorted(entity.env), deps, dry_run)

    if dry_run:  # pure preview — no gate, no render, no start
        return result

    # Real run: gate the substrate (Principle I — never assume up), refresh wiring, start CG.
    down = unreachable_deps(entity, prober)
    if down:
        raise LifecycleError(
            f"substrate not ready — unreachable: {', '.join(down)}. "
            "The DGX/rpg-lib substrate must be up before a campaign starts."
        )

    # Gate the campaign's mempalace store (003, FR-010): mneme up runs the runtime, but
    # refuses to start against a not-brought-up store — it never brings it up itself.
    reason = store_gate(cdir)
    if reason:
        raise LifecycleError(
            f"mempalace not brought up for '{campaign}': {reason} "
            f"— run `mneme mp bringup {campaign}`"
        )
    if render:
        _render.render_and_write_all(entity)
    env = {**os.environ, **entity.env}  # hypostasis env-wiring → CG's process
    out = runner(cmd, env)
    result.rc = out.returncode
    if out.returncode != 0:
        detail = (out.stderr or out.stdout or "").strip()[-300:]
        raise LifecycleError(f"CampaignGenerator start failed (rc {out.returncode}): {detail}")
    return result


def down(entity: ConfigEntity, campaign: str, *, port: int = 5000, runner: Runner = _run) -> None:
    cmd = [str(_cg_source(entity) / "stop"), "--port", str(port)]
    out = runner(cmd, dict(os.environ))
    if out.returncode != 0:
        detail = (out.stderr or out.stdout or "").strip()[-200:]
        raise LifecycleError(f"stop failed (rc {out.returncode}): {detail}")
