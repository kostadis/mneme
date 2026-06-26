"""Load the mneme-owned recipe (the shared best practice — FR-007/015).

Recipes ship in `mneme/recipes/` as `mempalace.recipe.<major>.yaml`. They are
read-only at runtime. `current()` returns the newest installed recipe; `load(version)`
returns a specific one — used by conformance to compare a campaign's adopted version.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from .models import MechanicalRules, Recipe, ScaffoldPattern, WingTemplate

RECIPES_DIR = Path(__file__).resolve().parent.parent / "recipes"
_FILE_RE = re.compile(r"^mempalace\.recipe\.v(\d+)\.yaml$")


class RecipeError(Exception):
    """A malformed or missing recipe."""


def _parse(raw: dict, source: Path) -> Recipe:
    version = str(raw.get("version", "")).strip()
    if not re.match(r"^\d+\.\d+\.\d+$", version):
        raise RecipeError(f"{source.name}: version must be semver, got {version!r}")

    mraw = raw.get("mechanical") or {}
    baseline = tuple(str(x) for x in (mraw.get("baseline_exclusions") or ()))
    if not baseline:
        raise RecipeError(f"{source.name}: mechanical.baseline_exclusions is required")
    mechanical = MechanicalRules(
        baseline_exclusions=baseline,
        mining_order=str(mraw.get("mining_order", "subscopes_before_root")),
        tunnel_rooms=tuple(str(x) for x in (mraw.get("tunnel_rooms") or ())),
        hazards=tuple(str(x) for x in (mraw.get("hazards") or ())),
    )

    scaffold: list[ScaffoldPattern] = []
    for praw in raw.get("scaffold") or ():
        wings = tuple(
            WingTemplate(
                name=str(w.get("name", "")),
                trust=str(w.get("trust", "reference")),
                source_hint=w.get("source_hint"),
                rooms_hint=tuple(str(r) for r in (w.get("rooms_hint") or ())),
            )
            for w in (praw.get("wings") or ())
        )
        scaffold.append(ScaffoldPattern(id=str(praw.get("id", "")), wings=wings))

    return Recipe(version=version, mechanical=mechanical, scaffold=tuple(scaffold))


def load_file(path: Path) -> Recipe:
    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except (OSError, yaml.YAMLError) as e:
        raise RecipeError(f"cannot read recipe {path}: {e}") from e
    if not isinstance(raw, dict):
        raise RecipeError(f"{path.name}: top level must be a mapping")
    return _parse(raw, path)


def available(recipes_dir: Path = RECIPES_DIR) -> dict[int, Path]:
    """Map major-version int → recipe file path, for every installed recipe."""
    out: dict[int, Path] = {}
    for p in recipes_dir.glob("mempalace.recipe.v*.yaml"):
        m = _FILE_RE.match(p.name)
        if m:
            out[int(m.group(1))] = p
    return out


def current(recipes_dir: Path = RECIPES_DIR) -> Recipe:
    """The newest installed recipe (highest major version)."""
    found = available(recipes_dir)
    if not found:
        raise RecipeError(f"no recipe found under {recipes_dir}")
    return load_file(found[max(found)])


def load(version: str, recipes_dir: Path = RECIPES_DIR) -> Recipe:
    """Load the recipe whose major version matches ``version`` (e.g. '1.0.0' → v1)."""
    major = int(version.split(".")[0])
    found = available(recipes_dir)
    if major not in found:
        raise RecipeError(f"recipe major v{major} not installed (have {sorted(found)})")
    return load_file(found[major])
