"""The wings a campaign had before it declared a corpus, remembered in the store (007, FR-018a).

`<store>/mneme-former-wings.json` is `{schema, campaign, recorded_at, wings: {name: trust}}`,
rewritten whenever `mp refresh` loads a wing-model authority that has a store (never by the
read-only `mp status`), so it holds the LAST pre-corpus wings. A store rebuilt (`mp regenerate`)
or first built (bring-up into a store that did not exist) from a corpus provably holds no
former wings, so those write it EMPTY (`wings: {}`, `try_record_empty`): `read` then returns a
FormerWings with no wings (distinct from None, "no record", which prune treats as fail-closed).
A corpus refresh/bring-up into an EXISTING store never writes it. It is a derived cache with
the store's lifecycle (a sibling of `mine_record.py`'s record) and feeds `mp prune`'s
former-canon guard. Writing is best effort (`try_record`): a failure is a warning string,
never a status or refresh failure.
"""

from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from mneme import atomic as _atomic

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
    return _atomic.write_json(record_path(store), doc, sort_keys=True)


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


def try_record_empty(store: Path, campaign: str) -> str | None:
    """Record that a store built from a corpus holds NO former wings (an empty record).
    None on success, else a warning string; never raises."""
    try:
        write(store, campaign, {})
    except OSError as e:
        return f"WARN could not record the (empty) former-wings record for the prune guard: {e}"
    return None
