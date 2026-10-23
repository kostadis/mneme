"""What the last corpus mines embedded, remembered in the store folder (007, R3, T019).

`<store>/mneme-corpus-mined.json` records, per file, the kind, the sha256 and the resolved
`target` that was actually mined. mempalace keeps no content hash, so this is the only place
"what content was embedded" lives. It is a DERIVED cache with the store's lifecycle
(`regenerate` wipes it), a sibling of `mine_record`'s `mneme-last-mine.json`, and like it a
top-level `.json`: neither a vector artifact, a binding, nor legacy chroma.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

FILENAME = "mneme-corpus-mined.json"
SCHEMA = 1


class CorpusRecordError(Exception):
    """The record exists but cannot be read."""


@dataclass(frozen=True)
class CorpusRecord:
    mined_at: str
    campaign: str
    corpus_sha256: str
    files: dict[str, dict] = field(default_factory=dict)  # relpath -> {kind, sha256, target}


def record_path(store: Path) -> Path:
    return Path(store) / FILENAME


def _atomic_write(store: Path, doc: dict) -> Path:
    store = Path(store)
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


def read(store: Path) -> CorpusRecord | None:
    """None when no record exists; CorpusRecordError when it exists but is unusable."""
    p = record_path(store)
    if not p.is_file():
        return None
    try:
        doc = json.loads(p.read_text())
        if doc.get("schema") != SCHEMA:
            raise ValueError(f"unsupported schema {doc.get('schema')!r}")
        files = doc["files"]
        if not isinstance(files, dict) or not all(
            isinstance(v, dict) and {"kind", "sha256", "target"} <= v.keys()
            for v in files.values()
        ):
            raise ValueError("malformed files map")
        return CorpusRecord(
            str(doc["mined_at"]), str(doc.get("campaign", "")),
            str(doc.get("corpus_sha256", "")), {str(k): dict(v) for k, v in files.items()},
        )
    except (OSError, ValueError, KeyError, AttributeError) as e:
        raise CorpusRecordError(f"{FILENAME} unreadable ({e})") from None


def write(
    store: Path,
    campaign: str,
    corpus_sha256: str,
    files: Mapping[str, Mapping],
    *,
    now: _dt.datetime | None = None,
) -> Path:
    """Atomically replace the whole record."""
    stamp = (now or _dt.datetime.now(_dt.UTC)).astimezone(_dt.UTC).isoformat(timespec="seconds")
    doc = {
        "schema": SCHEMA, "campaign": campaign, "mined_at": stamp,
        "corpus_sha256": corpus_sha256,
        "files": {k: {"kind": v["kind"], "sha256": v["sha256"], "target": v["target"]}
                  for k, v in sorted(files.items())},
    }
    return _atomic_write(store, doc)


def merge_kind(
    store: Path,
    campaign: str,
    corpus_sha256: str,
    kind: str,
    entries: Mapping[str, Mapping],
    *,
    now: _dt.datetime | None = None,
) -> Path:
    """Replace ``kind``'s entries with ``entries`` (relpath -> {kind, sha256, target}) and keep
    every other kind's. Called after each SUCCESSFUL kind mine (R3). An unreadable existing
    record is replaced rather than extended: it can no longer be trusted for the other kinds."""
    try:
        old = read(store)
    except CorpusRecordError:
        old = None
    kept = {k: v for k, v in (old.files if old else {}).items()
            if v.get("kind") != kind and k not in entries}
    kept.update({k: dict(v) for k, v in entries.items()})
    return write(store, campaign, corpus_sha256, kept, now=now)


def try_merge_kind(*args, **kwargs) -> str | None:
    """`merge_kind`, but an OSError becomes a warning string (the mine itself succeeded)."""
    try:
        merge_kind(*args, **kwargs)
    except OSError as e:
        return f"WARN could not record corpus mine: {e}"
    return None
