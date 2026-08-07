"""Load + validate the per-campaign authority (`.mneme/mempalace.yaml`).

The single editable source of truth for one campaign's mempalace (FR-002/016). Like
`hypostasis/config.py`, loading is tolerant and validation reports ALL problems at
once, raising AuthorityError before any side effect. The authority lives in the
campaign; mneme reads it and never invents its content (FR-020).
"""

from __future__ import annotations

import datetime as _dt
import os
from pathlib import Path

import yaml

from .models import (
    DISPOSITION_KINDS,
    TRUST_LEVELS,
    CampaignMempalaceConfig,
    Disposition,
    Room,
    StorePointer,
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


def default_mempalace_root() -> Path:
    """Fallback palace root when no entity is threaded in (tests, direct callers)."""
    return Path.home() / ".mempalace"


def store_path_for(alias: str, mempalace_root: Path | None = None) -> Path:
    """THE resolution rule (006, FR-011/011a): ``<mempalace_root>/palaces/<alias>``.

    Root-plus-alias is the only rule — there is no per-alias override table anywhere
    (Principle V). Redirecting a single palace is a filesystem concern: the derived
    location may be a symlink to the real one, followed transparently."""
    root = Path(mempalace_root) if mempalace_root else default_mempalace_root()
    return root / "palaces" / alias


def _parse(
    raw: dict, source: Path, problems: list[str], mempalace_root: Path | None = None
) -> CampaignMempalaceConfig:
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

    store = None
    sraw = raw.get("store")
    if isinstance(sraw, dict):
        alias = _normalize_wing_name(str(sraw.get("alias", campaign))) or campaign
        # The path is DERIVED, never read from the tracked file (006, FR-010/011). A `path:`
        # key here is legacy — kept only so `validate` can judge it (FR-013/014).
        store = StorePointer(alias=alias, path=store_path_for(alias, mempalace_root))

    return CampaignMempalaceConfig(
        campaign=campaign,
        recipe_version=recipe_version,
        wings=tuple(wings),
        extra_exclusions=tuple(str(x) for x in (raw.get("extra_exclusions") or ())),
        dispositions=dispositions,
        store=store,
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

    # Store pointer is optional at load (002-era authorities have none); if present it
    # must be well-formed. Bring-up enforces its *presence* via require_store (FR-013/016).
    if cfg.store is not None:
        if not cfg.store.alias:
            p.append("store.alias: empty")
        p += _legacy_store_path_problems(cfg, raw)

    return p


def _resolved(path: Path) -> Path:
    """Fully resolve for comparison — a sanctioned symlink redirect (FR-011a) must not read
    as a conflict, and neither must a trailing separator."""
    try:
        return path.resolve()
    except OSError:  # broken link / unreadable parent — compare what we can
        return Path(os.path.normpath(os.path.expanduser(str(path))))


def _legacy_store_path_problems(cfg: CampaignMempalaceConfig, raw: dict) -> list[str]:
    """Judge a pre-006 `store.path` still present in the tracked authority.

    Equal to the derived location → fine, and status reports it as owed cleanup (FR-013).
    Different → a hard problem naming both, on EVERY operation including read-only ones
    (FR-014). A conflicting path may name a real store full of real content; silently
    switching to the derived location would abandon it."""
    praw = (raw.get("store") or {}).get("path")
    if not praw:
        return []
    legacy = Path(os.path.expanduser(str(praw)))
    if _resolved(legacy) == _resolved(cfg.store.path):
        return []
    return [
        f"store.path '{praw}' conflicts with this host's derived location "
        f"'{cfg.store.path}'. The path is host-local and is no longer tracked (006): "
        "remove the `path:` key under `store:`. If the store really lives at the tracked "
        "location, move it or set data_roots.mempalace to that root first."
    ]


def require_store(cfg: CampaignMempalaceConfig) -> StorePointer:
    """Bring-up gate (FR-013/016): refuse a wings-but-no-store-pointer authority."""
    if cfg.store is None:
        raise AuthorityError(
            [f"campaign '{cfg.campaign}': no store pointer — bring-up requires one (FR-013/016)"]
        )
    return cfg.store


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
    }
    if cfg.store is not None:
        # Alias only. There is deliberately NO serializer for the path: that absence is what
        # makes it impossible to write a host-local location into a tracked file (FR-010,
        # SC-005) — the guarantee is structural, not a convention someone must remember.
        doc["store"] = {"alias": cfg.store.alias}
    doc["wings"] = [
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
        ]
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


def load(
    campaign_dir: Path, *, mempalace_root: Path | None = None
) -> CampaignMempalaceConfig:
    """Parse + validate the campaign's authority. Raises AuthorityError on any violation.

    ``mempalace_root`` is THIS host's palace root (006) — the store location is derived from
    it, never read from the tracked file. Callers with a ConfigEntity pass
    ``hypostasis.config.mempalace_root(entity)``; the default keeps direct callers working."""
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
    cfg = _parse(raw, path, problems, mempalace_root)
    problems += validate(cfg, raw, campaign_dir)
    if problems:
        raise AuthorityError(problems)
    return cfg


def has_legacy_store_path(campaign_dir: Path) -> bool:
    """True if the tracked authority still carries the removed `store.path` key (FR-013).

    Read-only and tolerant: status uses it to report owed cleanup. A *conflicting* legacy
    path never reaches here — `validate` fails the load outright (FR-014)."""
    try:
        raw = yaml.safe_load(authority_path(campaign_dir).read_text()) or {}
    except (OSError, yaml.YAMLError):
        return False
    return isinstance(raw, dict) and bool((raw.get("store") or {}).get("path"))
