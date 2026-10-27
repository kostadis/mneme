"""Refusals for the wing-editing commands on a corpus campaign (007 US4, FR-001a, FR-019).

A corpus campaign declares what is mined in `.mneme/corpus.yaml` and has no wings, so any
command whose job is to write or reshape wings must say so and stop. Each refusal names the
command and the reason (T042).
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import yaml

from mneme.corpus.config import CorpusConfigError, corpus_path
from mneme.corpus.config import load as _load_corpus

from .runner import MempalaceError


class CorpusRefusal(MempalaceError):
    """A wing-editing command met a corpus campaign."""


def refusal(command: str, campaign: str, reason: str) -> CorpusRefusal:
    return CorpusRefusal(
        f"`mneme mp {command}` refused for {campaign}: it is a corpus campaign "
        f"(.mneme/corpus.yaml declares what is mined, and it has no wings) — {reason}"
    )


def shadowed_kinds(campaign_dir: Path, recipe) -> list[str]:
    """Campaign kinds in this campaign's corpus.yaml whose names the ``recipe`` makes standard
    kinds. Adopting that recipe moves them to `kinds:` (see ``migrate_shadowed``). Unreadable
    YAML yields none (not this check's job; `mneme corpus check` reports it)."""
    try:
        raw = yaml.safe_load(corpus_path(campaign_dir).read_text()) or {}
    except (OSError, yaml.YAMLError):
        return []
    camp = raw.get("campaign_kinds") if isinstance(raw, dict) else None
    if not isinstance(camp, dict):
        return []
    standard = {k.name for k in recipe.kinds}
    return sorted(str(n) for n in camp if str(n) in standard)


def migrate_shadowed(
    command: str, campaign: str, campaign_dir: Path, recipe,
) -> tuple[str, list[str]] | None:
    """The new text of corpus.yaml after moving every campaign kind the ``recipe`` makes
    standard from `campaign_kinds:` to `kinds:` (bodies untouched, an explicit trust kept even
    when it equals the default), plus the moved names. ``None`` when nothing moves.

    Writes nothing. Refuses (CorpusRefusal) when a moved name is already under `kinds:` or when
    the rewritten file does not validate against ``recipe``."""
    moved = shadowed_kinds(campaign_dir, recipe)
    if not moved:
        return None
    raw = yaml.safe_load(corpus_path(campaign_dir).read_text())
    kinds = raw.get("kinds")
    if kinds is not None and not isinstance(kinds, dict):
        raise refusal(command, campaign, "`kinds:` is not a mapping; nothing was written")
    kinds = dict(kinds or {})
    camp = dict(raw["campaign_kinds"])
    for n in moved:
        if n in kinds:
            raise refusal(
                command, campaign,
                f"shadowed-kind: '{n}' is declared under both `kinds:` and `campaign_kinds:`; "
                "nothing was written",
            )
    for key in list(camp):
        if str(key) in moved:
            kinds[key] = camp.pop(key)
    raw["kinds"] = kinds
    if camp:
        raw["campaign_kinds"] = camp
    else:
        del raw["campaign_kinds"]
    text = yaml.safe_dump(raw, sort_keys=False, default_flow_style=False)
    with tempfile.TemporaryDirectory() as td:  # validate before anything real is written
        scratch = Path(td)
        (scratch / ".mneme").mkdir()
        corpus_path(scratch).write_text(text)
        auth = campaign_dir / ".mneme" / "mempalace.yaml"
        if auth.exists():
            shutil.copy(auth, scratch / ".mneme" / "mempalace.yaml")
        try:
            _load_corpus(scratch, recipe)
        except CorpusConfigError as e:
            raise refusal(
                command, campaign,
                f"moving {', '.join(moved)} to `kinds:` leaves corpus.yaml invalid under recipe "
                f"{recipe.version} ({e}); nothing was written",
            ) from e
    return text, moved
