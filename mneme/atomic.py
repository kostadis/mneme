"""Atomic JSON file replacement, shared by the store records and the TOC snapshot."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

_TEMP_PREFIX, _TEMP_SUFFIX = ".", ".tmp"


def is_temp(name: str) -> bool:
    """True for the temp file name `write_json` leaves behind when a write was interrupted
    (`.<final name>.<rand>.tmp`)."""
    return name.startswith(_TEMP_PREFIX) and name.endswith(_TEMP_SUFFIX)


def write_json(path: Path, doc: dict, *, sort_keys: bool = False) -> Path:
    """Write ``doc`` to ``path`` via a sibling temp file + `os.replace`; creates the parent
    directory. A failure leaves no temp file behind and the old file untouched."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=path.parent, prefix=f"{_TEMP_PREFIX}{path.name}.", suffix=_TEMP_SUFFIX
    )
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(doc, fh, indent=2, sort_keys=sort_keys)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return path
