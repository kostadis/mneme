"""Refusals for the wing-editing commands on a corpus campaign (007 US4, FR-001a, FR-019).

A corpus campaign declares what is mined in `.mneme/corpus.yaml` and has no wings, so any
command whose job is to write or reshape wings must say so and stop. Each refusal names the
command and the reason (T042).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from mneme.corpus.config import corpus_path

from .runner import MempalaceError


class CorpusRefusal(MempalaceError):
    """A wing-editing command met a corpus campaign."""


def refusal(command: str, campaign: str, reason: str) -> CorpusRefusal:
    return CorpusRefusal(
        f"`mneme mp {command}` refused for {campaign}: it is a corpus campaign "
        f"(.mneme/corpus.yaml declares what is mined, and it has no wings) — {reason}"
    )


def shadowed_kinds(campaign_dir: Path, recipe) -> list[str]:
    """Campaign kinds in this campaign's corpus.yaml whose names the ``recipe`` would make
    standard kinds. Adopting such a recipe would silently change their meaning, so the caller
    reports `shadowed-kind` instead of writing. Unreadable YAML yields none (not this check's
    job; `mneme corpus check` reports it)."""
    try:
        raw = yaml.safe_load(corpus_path(campaign_dir).read_text()) or {}
    except (OSError, yaml.YAMLError):
        return []
    camp = raw.get("campaign_kinds") if isinstance(raw, dict) else None
    if not isinstance(camp, dict):
        return []
    standard = {k.name for k in recipe.kinds}
    return sorted(str(n) for n in camp if str(n) in standard)
