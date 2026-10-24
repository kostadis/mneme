"""What the last corpus mines embedded, remembered in the store folder (007, R3, T019).

`<store>/mneme-corpus-mined.json` records, per file, the kind, the sha256 and the resolved
`target` that was actually mined. mempalace keeps no content hash, so this is the only place
"what content was embedded" lives. It is a DERIVED cache with the store's lifecycle
(`regenerate` wipes it), a sibling of `mine_record`'s `mneme-last-mine.json`, and like it a
top-level `.json`: neither a vector artifact, a binding, nor legacy chroma.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from mneme import atomic as _atomic

FILENAME = "mneme-corpus-mined.json"
SCHEMA = 1


class CorpusRecordError(Exception):
    """The record exists but cannot be read."""


@dataclass(frozen=True)
class CorpusRecord:
    mined_at: str
    campaign: str
    corpus_sha256: str
    # relpath -> {kind, sha256, target[, skipped]}; `skipped` is mempalace's reason code for a
    # file it did NOT mine (the entry's sha256 is the content that was skipped)
    files: dict[str, dict] = field(default_factory=dict)
    # sha256 of the root mempalace.yaml (where `excluded` comes from) when the files were mined;
    # None in a record that predates it
    excludes_sha256: str | None = None


def record_path(store: Path) -> Path:
    return Path(store) / FILENAME


def excludes_digest(campaign_dir: Path) -> str:
    """sha256 of the campaign's root mempalace.yaml bytes (a sentinel when it is absent):
    content, not mtime, so a re-render of the same text or a `git checkout` changes nothing."""
    try:
        return hashlib.sha256((Path(campaign_dir) / "mempalace.yaml").read_bytes()).hexdigest()
    except OSError:
        return hashlib.sha256(b"").hexdigest() + "-absent"


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
            and isinstance(v.get("skipped", ""), str)
            and isinstance(v["sha256"], str) and isinstance(v["kind"], str)
            and (v["target"] is None or isinstance(v["target"], str))
            for v in files.values()
        ):
            raise ValueError("malformed files map")
        excludes = doc.get("excludes_sha256")
        if excludes is not None and not isinstance(excludes, str):
            raise ValueError("malformed excludes_sha256")
        return CorpusRecord(
            str(doc["mined_at"]), str(doc.get("campaign", "")),
            str(doc.get("corpus_sha256", "")), {str(k): dict(v) for k, v in files.items()},
            excludes,
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
    excludes_sha256: str | None = None,
) -> Path:
    """Atomically replace the whole record."""
    stamp = (now or _dt.datetime.now(_dt.UTC)).astimezone(_dt.UTC).isoformat(timespec="seconds")
    doc = {
        "schema": SCHEMA, "campaign": campaign, "mined_at": stamp,
        "corpus_sha256": corpus_sha256,
        "files": {k: {f: v[f] for f in ("kind", "sha256", "target", "skipped") if f in v}
                  for k, v in sorted(files.items())},
    }
    if excludes_sha256 is not None:
        doc["excludes_sha256"] = excludes_sha256
    return _atomic.write_json(record_path(store), doc, sort_keys=True)


def merge_kind(
    store: Path,
    campaign: str,
    corpus_sha256: str,
    kind: str,
    entries: Mapping[str, Mapping],
    *,
    now: _dt.datetime | None = None,
    excludes_sha256: str | None = None,
) -> Path:
    """Replace ``kind``'s entries with ``entries`` (relpath -> {kind, sha256, target[, skipped]})
    and keep every other kind's. Called after each SUCCESSFUL kind mine (R3). An unreadable existing
    record is replaced rather than extended: it can no longer be trusted for the other kinds."""
    try:
        old = read(store)
    except CorpusRecordError:
        old = None
    kept = {k: v for k, v in (old.files if old else {}).items()
            if v.get("kind") != kind and k not in entries}
    if old is not None and old.excludes_sha256 != excludes_sha256:
        # the other kinds' `excluded` skips were decided under rules that no longer hold; one
        # digest cannot vouch for both, so forget them (a refresh retries those files)
        kept = {k: v for k, v in kept.items() if v.get("skipped") != "excluded"}
    kept.update({k: dict(v) for k, v in entries.items()})
    return write(store, campaign, corpus_sha256, kept, now=now, excludes_sha256=excludes_sha256)


def try_merge_kind(*args, **kwargs) -> str | None:
    """`merge_kind`, but an OSError becomes a warning string (the mine itself succeeded)."""
    try:
        merge_kind(*args, **kwargs)
    except OSError as e:
        return f"WARN could not record corpus mine: {e}"
    return None
