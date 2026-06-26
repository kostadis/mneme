"""Refresh campaign indexes from each campaign's own configuration (US1, FR-003/004).

Orchestrates `mempalace mine` per wing in sub-scopes-before-root order, using the
wings the campaign already has. A campaign with no wings is *skipped* (not failed);
a campaign whose mining fails is isolated so the run continues for the others
(FR-006). Mining is idempotent (FR-014). Reads the live active checkout (FR-019);
writes only the index, never the campaign repo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from hypostasis.models import ConfigEntity

from . import discover as _discover
from .discover import CampaignRef
from .runner import MempalaceError, MempalaceRunner


@dataclass
class RefreshResult:
    campaign: str
    wings: list[str] = field(default_factory=list)  # rel paths mined (or planned)
    skipped: bool = False
    failed: bool = False
    error: str = ""
    dry_run: bool = False

    def line(self) -> str:
        if self.skipped:
            return f"{self.campaign:24} SKIP   no wings configured"
        if self.failed:
            return f"{self.campaign:24} FAIL   {self.error}"
        verb = "PLAN" if self.dry_run else "OK"
        return f"{self.campaign:24} {verb:6} mined: {', '.join(self.wings) or '(none)'}"


def _refresh_one(ref: CampaignRef, runner: MempalaceRunner, dry_run: bool) -> RefreshResult:
    result = RefreshResult(campaign=ref.name, dry_run=dry_run)
    if not ref.wing_dirs:
        result.skipped = True
        return result
    # discover returns wing dirs deepest-first → sub-scopes before root (FR-004).
    for wing_dir in ref.wing_dirs:
        rel = str(wing_dir.relative_to(ref.path)) or "."
        try:
            runner.mine(wing_dir, dry_run=dry_run)
            result.wings.append(rel)
        except MempalaceError as e:
            result.failed = True
            result.error = str(e)
            return result
    return result


def refresh(
    entity: ConfigEntity,
    campaign: str | None = None,
    *,
    dry_run: bool = False,
    runner: MempalaceRunner | None = None,
) -> list[RefreshResult]:
    """Refresh one campaign (``campaign`` set) or all (``campaign`` None)."""
    runner = runner or MempalaceRunner.for_venv(_venv(entity))
    refs = [_discover.find(entity, campaign)] if campaign else _discover.discover(entity)
    return [_refresh_one(ref, runner, dry_run) for ref in refs]


def _venv(entity: ConfigEntity) -> Path | None:
    return entity.venv if entity.venv and str(entity.venv) != "." else None
