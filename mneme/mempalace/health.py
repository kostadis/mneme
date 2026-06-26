"""Observed store health + on-disk inspection (003, D5/D6).

turbovec store: the bindings (`turbovec/<collection>/store.sqlite3` + `knowledge_graph.sqlite3`)
are the source of truth; `index.tvim` is a rebuildable cache; `chroma.sqlite3` + segments are
dead migration legacy. Health = present + the store opens cleanly (turbovec consistency, asked of
`mempalace status` — D6). Feeds the `mneme up` gate and `mneme mp status` (Principle I/IX).
"""

from __future__ import annotations

from pathlib import Path

from .models import DedicatedStore, StoreHealth, StoreState
from .runner import MempalaceRunner


def inspect(store_path: Path) -> DedicatedStore:
    """Classify a store dir's files into bindings / rebuildable / legacy (no I/O beyond stat)."""
    store_path = Path(store_path)
    bindings: list[Path] = sorted(store_path.glob("turbovec/*/store.sqlite3"))
    kg = store_path / "knowledge_graph.sqlite3"
    if kg.is_file():
        bindings.append(kg)
    rebuildable = sorted(store_path.glob("turbovec/*/index.tvim"))
    legacy: list[Path] = []
    chroma = store_path / "chroma.sqlite3"
    if chroma.is_file():
        legacy.append(chroma)
    # "present" = the store dir holds at least one bindings file (a turbovec store.sqlite3)
    present = store_path.is_dir() and any(p.name == "store.sqlite3" for p in bindings)
    return DedicatedStore(
        path=store_path,
        present=present,
        bindings_files=tuple(bindings),
        rebuildable_files=tuple(rebuildable),
        legacy_files=tuple(legacy),
    )


def health(store_path: Path, *, runner: MempalaceRunner | None = None) -> StoreHealth:
    """Observed health of the store. MISSING if no bindings; HEALTHY iff it opens cleanly."""
    ds = inspect(store_path)
    if not ds.present:
        return StoreHealth(
            present=False, state=StoreState.MISSING, note=f"no store at {store_path}"
        )
    runner = runner or MempalaceRunner.for_venv(None)
    if runner.status(store_path):
        return StoreHealth(present=True, state=StoreState.HEALTHY, note="store opens cleanly")
    return StoreHealth(
        present=True, state=StoreState.DEGRADED, note="store present but not consistent/openable"
    )
