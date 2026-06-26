"""Execute a human-approved migration plan (US5, FR-023/024/025/026).

The plan is reasoned out freely by an assistant and approved by the human; mneme
executes it in the working copy under three guarantees independent of the plan:
content stays **verbatim** (FR-025 — a closed, content-preserving op set; no
`rewrite_content`), writes are isolated to the working copy (FR-018), and the actual
resulting index/config is **verified** afterward (FR-026).
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from . import authority as _authority
from . import conform as _conform
from . import recipe as _recipe
from . import render as _render
from .models import CONTENT_PRESERVING_OPS, MigrationPlan, State
from .runner import MempalaceRunner


class MigrationError(Exception):
    """A migration plan was invalid or a step violated the verbatim guarantee."""


@dataclass
class MigrationResult:
    campaign: str
    executed: list[str] = field(default_factory=list)
    conformant: bool = False
    note: str = ""


def validate_plan(plan: MigrationPlan) -> list[str]:
    problems: list[str] = []
    if not plan.approved_by_human:
        problems.append("plan is not approved_by_human — refusing to execute (FR-024)")
    for i, step in enumerate(plan.steps):
        if step.op not in CONTENT_PRESERVING_OPS:
            problems.append(
                f"step {i}: op '{step.op}' is not content-preserving "
                f"(allowed: {', '.join(CONTENT_PRESERVING_OPS)}) — refused (FR-025)"
            )
    return problems


# ── step executors (every one preserves document bytes) ──────────────────────


def _op_move(campaign_dir: Path, args: dict) -> None:
    src = campaign_dir / args["src"]
    dst = campaign_dir / args["dst"]
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))


_op_rename = _op_move


def _op_split(campaign_dir: Path, args: dict) -> None:
    """Split a bible into chapter files on a heading marker, VERBATIM.

    The concatenation of the chapter files (in order) must equal the source byte for
    byte (FR-025) — asserted before the source is removed.
    """
    src = campaign_dir / args["src"]
    into = campaign_dir / args["into"]
    marker = args.get("on", "# ")
    text = src.read_text()
    into.mkdir(parents=True, exist_ok=True)

    chunks: list[str] = []
    current: list[str] = []
    for line in text.splitlines(keepends=True):
        if line.startswith(marker) and current:
            chunks.append("".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        chunks.append("".join(current))

    if "".join(chunks) != text:
        raise MigrationError(f"split of {args['src']} would not be verbatim — refused")

    for i, chunk in enumerate(chunks, 1):
        (into / f"chapter_{i:02d}.md").write_text(chunk)
    src.unlink()


def _op_reindex(campaign_dir: Path, args: dict) -> None:
    # No file change — the actual re-mine happens on refresh after adoption.
    return None


def _op_write_authority(campaign_dir: Path, args: dict) -> None:
    (campaign_dir / ".mneme").mkdir(parents=True, exist_ok=True)
    _authority.authority_path(campaign_dir).write_text(args["content"])


_EXECUTORS = {
    "move": _op_move,
    "rename": _op_rename,
    "split": _op_split,
    "reindex": _op_reindex,
    "write_authority": _op_write_authority,
}


def apply_plan(plan: MigrationPlan, campaign_dir: Path) -> list[str]:
    """Execute every step in ``campaign_dir`` (a working copy). Returns step labels."""
    problems = validate_plan(plan)
    if problems:
        raise MigrationError("; ".join(problems))
    executed: list[str] = []
    for step in plan.steps:
        _EXECUTORS[step.op](campaign_dir, step.args)
        executed.append(f"{step.op} {step.args.get('src', step.args.get('wing', ''))}".strip())
    return executed


def verify(campaign_dir: Path, *, runner: MempalaceRunner | None = None) -> tuple[bool, str]:
    """Confirm the ACTUAL resulting config/index conforms (FR-026). Distinguishes
    'migration incomplete' (stale render / no authority) from a deliberate difference."""
    report = _conform.check_dir(campaign_dir, runner=runner)
    # For *verification* (unlike status), a config-less result is incomplete — a
    # migration was supposed to leave a usable mempalace, so MISSING_CONFIG counts.
    incomplete_states = {State.STALE_RENDER, State.MISSING_CONFIG, State.INVALID_CONFIG}
    incomplete = [r for r in report.rows if r.state in incomplete_states]
    bad = [r for r in report.rows if not r.ok and r not in incomplete]
    if not incomplete and not bad:
        return True, "migration verified: campaign conforms"
    flagged = incomplete + bad
    detail = "; ".join(f"{r.dimension}:{r.state.value}" for r in flagged)
    if incomplete:
        return False, f"migration INCOMPLETE: {detail}"
    return False, f"result diverges (deliberate?): {detail}"


def migrate_in_dir(
    plan: MigrationPlan, campaign_dir: Path, *, runner: MempalaceRunner | None = None
) -> MigrationResult:
    """Apply + verify a plan in a campaign dir (the working copy). Re-render derived
    files from the (possibly updated) authority so verification reflects reality."""
    result = MigrationResult(campaign=plan.campaign)
    result.executed = apply_plan(plan, campaign_dir)
    if _authority.has_authority(campaign_dir):
        cfg = _authority.load(campaign_dir)
        _render.write_all(cfg, _recipe.load(cfg.recipe_version), campaign_dir)
    result.conformant, result.note = verify(campaign_dir, runner=runner)
    return result
