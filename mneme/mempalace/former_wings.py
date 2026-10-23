"""The wings a campaign had before it declared a corpus, remembered in the store (007, FR-018a).

`<store>/mneme-former-wings.json` is `{schema, campaign, recorded_at, wings: {name: trust}}`,
rewritten whenever mneme loads a wing-model authority that has a store, so it holds the LAST
pre-corpus wings. It is a derived cache with the store's lifecycle (a sibling of
`mine_record.py`'s record) and feeds `mp prune`'s former-canon guard. Writing is best effort
(`try_record`): a failure is a warning string, never a status or refresh failure.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

FILENAME = "mneme-former-wings.json"
SCHEMA = 1


class FormerWingsError(Exception):
    """The record exists but cannot be read."""


@dataclass(frozen=True)
class FormerWings:
    recorded_at: str
    campaign: str
    wings: dict[str, str] = field(default_factory=dict)  # wing name -> trust

    def authoritative(self) -> frozenset[str]:
        return frozenset(n for n, t in self.wings.items() if t == "authoritative")


def record_path(store: Path) -> Path:
    return Path(store) / FILENAME


def write(
    store: Path, campaign: str, wings: Mapping[str, str], *, now: _dt.datetime | None = None
) -> Path:
    """Atomically replace the record."""
    store = Path(store)
    stamp = (now or _dt.datetime.now(_dt.UTC)).astimezone(_dt.UTC).isoformat(timespec="seconds")
    doc = {"schema": SCHEMA, "campaign": campaign, "recorded_at": stamp,
           "wings": {str(k): str(v) for k, v in sorted(wings.items())}}
    store.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=store, prefix=f".{FILENAME}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(doc, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, record_path(store))
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return record_path(store)


def read(store: Path) -> FormerWings | None:
    """None when no record exists; FormerWingsError when it exists but is unusable."""
    p = record_path(store)
    if not p.is_file():
        return None
    try:
        doc = json.loads(p.read_text())
        if doc.get("schema") != SCHEMA:
            raise ValueError(f"unsupported schema {doc.get('schema')!r}")
        wings = doc["wings"]
        if not isinstance(wings, dict):
            raise ValueError("malformed wings map")
        return FormerWings(
            str(doc.get("recorded_at", "")), str(doc.get("campaign", "")),
            {str(k): str(v) for k, v in wings.items()},
        )
    except (OSError, ValueError, KeyError, AttributeError) as e:
        raise FormerWingsError(f"{FILENAME} unreadable ({e})") from None


def try_record(cfg) -> str | None:
    """Record a wing-model authority's wings if it has an existing store; None on success or
    when there is nothing to record, else a warning string. Never creates the store."""
    if cfg.store is None or not cfg.wings or not Path(cfg.store.path).is_dir():
        return None
    try:
        write(cfg.store.path, cfg.campaign, {w.name: w.trust for w in cfg.wings})
    except OSError as e:
        return f"WARN could not record the campaign's wings for the prune guard: {e}"
    return None
