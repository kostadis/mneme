"""The last mine's skipped files, remembered in the store folder (GH #31 — Principles I, IX).

`<store>/mneme-last-mine.json` is a DERIVED cache with the store's lifecycle: `regenerate`
wipes the store and the next mine rewrites it. It is a top-level `.json`, so it is neither a
vector artifact (embedder guard), a binding (backup), nor legacy chroma (drop-legacy).
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .mine_report import WingSkips

FILENAME = "mneme-last-mine.json"
SCHEMA = 1


class MineRecordError(Exception):
    """The record exists but cannot be read."""


@dataclass(frozen=True)
class MineRecord:
    mined_at: str
    campaign: str
    wings: dict[str, list[dict]]  # wing -> [{name, kind, detail}]
    status: str = "ok"  # "ok" | "failed" (a later wing failed; wings holds the partial skips)
    error: str = ""
    carried_over: str = ""  # e.g. "restore 20261004-101500"

    @property
    def names(self) -> list[str]:
        return [e["name"] for entries in self.wings.values() for e in entries]


def record_path(store: Path) -> Path:
    return Path(store) / FILENAME


def write(
    store: Path,
    campaign: str,
    wings: list[str],
    skips: WingSkips,
    *,
    now: _dt.datetime | None = None,
    status: str = "ok",
    error: str = "",
) -> Path:
    """Atomically record this operation's skips. Every mined wing gets a list (possibly empty)
    so status can say "no gaps" rather than "unknown"."""
    by_wing: dict[str, list[dict]] = {w: [] for w in wings}
    for wing, n in skips:
        by_wing.setdefault(wing, []).append({"name": n.name, "kind": n.kind, "detail": n.detail})
    stamp = (now or _dt.datetime.now(_dt.UTC)).astimezone(_dt.UTC).isoformat(timespec="seconds")
    doc = {"schema": SCHEMA, "mined_at": stamp, "campaign": campaign, "wings": by_wing}
    doc["status"] = status
    if error:
        doc["error"] = error[:500]
    store = Path(store)
    store.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=store, prefix=f".{FILENAME}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(doc, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, record_path(store))
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return record_path(store)


def read(store: Path) -> MineRecord | None:
    """None when no record exists; MineRecordError when it exists but is unusable."""
    p = record_path(store)
    if not p.is_file():
        return None
    try:
        doc = json.loads(p.read_text())
        if doc.get("schema") != SCHEMA:
            raise ValueError(f"unsupported schema {doc.get('schema')!r}")
        wings = doc["wings"]
        if not isinstance(wings, dict) or not all(
            isinstance(v, list) and all(isinstance(e, dict) and "name" in e for e in v)
            for v in wings.values()
        ):
            raise ValueError("malformed wings map")
        return MineRecord(
            str(doc["mined_at"]), str(doc.get("campaign", "")), wings,
            str(doc.get("status", "ok")), str(doc.get("error", "")),
            str(doc.get("carried_over", "")),
        )
    except (OSError, ValueError, KeyError, AttributeError) as e:
        raise MineRecordError(f"{FILENAME} unreadable ({e})") from None


def try_write(*args, **kwargs) -> str | None:
    """`write`, but an OSError becomes a warning string instead of crashing the mine (the mine
    itself already succeeded or failed on its own terms)."""
    try:
        write(*args, **kwargs)
    except OSError as e:
        return f"WARN could not record mine skips: {e}"
    return None


def carry_over(old_store: Path, new_store: Path, label: str) -> bool:
    """Copy a record from a replaced store into the restored one, marked ``carried_over``.
    Skips are a property of the sources, which a restore does not change. Best effort."""
    try:
        doc = json.loads(record_path(old_store).read_text())
        if not isinstance(doc, dict) or "wings" not in doc:
            return False
        doc["carried_over"] = label
        record_path(new_store).write_text(json.dumps(doc, indent=2) + "\n")
        return read(new_store) is not None
    except (OSError, ValueError, MineRecordError):
        return False
