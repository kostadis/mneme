"""Load + validate the per-campaign authority (`.mneme/mempalace.yaml`).

The single editable source of truth for one campaign's mempalace (FR-002/016). Like
`hypostasis/config.py`, loading is tolerant and validation reports ALL problems at
once, raising AuthorityError before any side effect. The authority lives in the
campaign; mneme reads it and never invents its content (FR-020).
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

import yaml

from .models import (
    DISPOSITION_KINDS,
    TRUST_LEVELS,
    CampaignMempalaceConfig,
    Disposition,
    Room,
    Wing,
)

AUTHORITY_RELPATH = Path(".mneme") / "mempalace.yaml"

# Fields that would establish a SECOND store of derived/observed truth in the
# authority (mirrors hypostasis FORBIDDEN_TOP_LEVEL — Principle III/V).
FORBIDDEN_TOP_LEVEL = ("rendered", "index", "mined_at", "mine_timestamps", "stamp")


class AuthorityError(Exception):
    """Schema / integrity violation in `.mneme/mempalace.yaml`."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("invalid .mneme/mempalace.yaml:\n  - " + "\n  - ".join(problems))


def authority_path(campaign_dir: Path) -> Path:
    return campaign_dir / AUTHORITY_RELPATH


def has_authority(campaign_dir: Path) -> bool:
    return authority_path(campaign_dir).is_file()


def _normalize_wing_name(name: str) -> str:
    """mempalace's rule: lowercase, collapse '-'/space to '_'."""
    return name.strip().lower().replace("-", "_").replace(" ", "_")


def _parse(raw: dict, source: Path, problems: list[str]) -> CampaignMempalaceConfig:
    campaign = str(raw.get("campaign", "")).strip()
    if not campaign:
        problems.append("missing required field: campaign")
    recipe_version = str(raw.get("recipe_version", "")).strip()
    if not recipe_version:
        problems.append("missing required field: recipe_version")

    wings: list[Wing] = []
    for w in raw.get("wings") or ():
        w = w or {}
        name = _normalize_wing_name(str(w.get("name", "")))
        rooms = tuple(
            Room(
                name=_normalize_wing_name(str(r.get("name", ""))),
                description=str(r.get("description", "")),
                keywords=tuple(str(k) for k in (r.get("keywords") or ())),
            )
            for r in (w.get("rooms") or ())
        )
        wings.append(
            Wing(
                name=name,
                source=str(w.get("source", "")).strip(),
                trust=str(w.get("trust", "reference")),
                rooms=rooms,
            )
        )

    dispositions = tuple(
        Disposition(
            divergence=str(d.get("divergence", "")),
            kind=str(d.get("kind", "")),
            recorded=str(d.get("recorded", "")),
            rationale=str(d.get("rationale", "")),
        )
        for d in (raw.get("dispositions") or ())
    )

    return CampaignMempalaceConfig(
        campaign=campaign,
        recipe_version=recipe_version,
        wings=tuple(wings),
        extra_exclusions=tuple(str(x) for x in (raw.get("extra_exclusions") or ())),
        dispositions=dispositions,
        source_path=source,
    )


def _is_iso_date(value: str) -> bool:
    try:
        _dt.date.fromisoformat(value)
        return True
    except ValueError:
        return False


def validate(cfg: CampaignMempalaceConfig, raw: dict, campaign_dir: Path) -> list[str]:
    p: list[str] = []

    for key in FORBIDDEN_TOP_LEVEL:
        if key in raw:
            p.append(f"forbidden field '{key}': derived/observed truth is never stored here")

    if not cfg.wings:
        p.append("wings: at least one wing is required")

    seen: set[str] = set()
    for w in cfg.wings:
        if not w.name:
            p.append("wing: a wing has an empty name")
        elif w.name in seen:
            p.append(f"wing '{w.name}': duplicate wing name")
        seen.add(w.name)
        if w.trust not in TRUST_LEVELS:
            p.append(f"wing '{w.name}': trust '{w.trust}' not in {TRUST_LEVELS}")
        if not w.source:
            p.append(f"wing '{w.name}': missing source")
        elif not (campaign_dir / w.source).is_dir():
            p.append(f"wing '{w.name}': source '{w.source}' does not exist under the campaign")

    # Sub-scopes-before-root invariant (FR-004): the root wing (source '.') must be
    # last, and no wing source may be an ancestor of a later wing's source.
    sources = [w.source for w in cfg.wings]
    for i, src in enumerate(sources):
        for later in sources[i + 1 :]:
            if src == "." or _is_ancestor(src, later):
                p.append(
                    f"wing order: '{src}' encloses a later wing '{later}' — "
                    "sub-scopes must be listed before the enclosing scope (FR-004)"
                )

    for d in cfg.dispositions:
        if not d.divergence:
            p.append("disposition: empty divergence key")
        if d.kind not in DISPOSITION_KINDS:
            p.append(f"disposition '{d.divergence}': kind must be one of {DISPOSITION_KINDS}")
        if d.kind == "deliberate" and not d.rationale:
            p.append(f"disposition '{d.divergence}': kind 'deliberate' requires a rationale")
        if d.recorded and not _is_iso_date(d.recorded):
            p.append(f"disposition '{d.divergence}': recorded '{d.recorded}' is not an ISO date")

    return p


def _is_ancestor(maybe_parent: str, child: str) -> bool:
    parent = Path(maybe_parent)
    try:
        Path(child).relative_to(parent)
        return parent != Path(child)
    except ValueError:
        return False


def to_yaml(cfg: CampaignMempalaceConfig) -> str:
    """Serialize an authority back to YAML (for bootstrap/upgrade writes)."""
    doc: dict = {
        "campaign": cfg.campaign,
        "recipe_version": cfg.recipe_version,
        "wings": [
            {
                "name": w.name,
                "source": w.source,
                "trust": w.trust,
                "rooms": [
                    {"name": r.name, "description": r.description, "keywords": list(r.keywords)}
                    for r in w.rooms
                ],
            }
            for w in cfg.wings
        ],
    }
    if cfg.extra_exclusions:
        doc["extra_exclusions"] = list(cfg.extra_exclusions)
    if cfg.dispositions:
        doc["dispositions"] = [
            {"divergence": d.divergence, "kind": d.kind, "rationale": d.rationale,
             "recorded": d.recorded}
            for d in cfg.dispositions
        ]
    return yaml.safe_dump(doc, sort_keys=False, default_flow_style=False)


def write(cfg: CampaignMempalaceConfig, campaign_dir: Path) -> Path:
    """Write the authority into ``campaign_dir/.mneme/mempalace.yaml`` (a working copy)."""
    path = authority_path(campaign_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_yaml(cfg))
    return path


def load(campaign_dir: Path) -> CampaignMempalaceConfig:
    """Parse + validate the campaign's authority. Raises AuthorityError on any violation."""
    path = authority_path(campaign_dir)
    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except FileNotFoundError as e:
        raise AuthorityError([f"no authority at {path}"]) from e
    except yaml.YAMLError as e:
        raise AuthorityError([f"YAML parse error: {e}"]) from e
    if not isinstance(raw, dict):
        raise AuthorityError(["top level of .mneme/mempalace.yaml must be a mapping"])

    problems: list[str] = []
    cfg = _parse(raw, path, problems)
    problems += validate(cfg, raw, campaign_dir)
    if problems:
        raise AuthorityError(problems)
    return cfg
