#!/usr/bin/env python3
"""A recording stub for the `mempalace` CLI (test double).

Records each invocation (argv) as a line in ``$MNEME_STUB_LOG`` and emits canned
output so `mneme`'s subprocess orchestration can be tested without a real palace.

- ``mine <path> [--dry-run]``  → exit 0, logs the call.
- ``sync <path> --dry-run``    → prints drift: ``DRIFT`` if a sibling marker file
  ``<path>/.stub_drift`` exists, else ``CLEAN`` (lets a test simulate staleness).
- ``status``                   → exit 0.
- ``split ...``                → exit 0, logs the call.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    argv = sys.argv[1:]
    log = os.environ.get("MNEME_STUB_LOG")
    if log:
        with open(log, "a") as fh:
            fh.write(" ".join(argv) + "\n")

    if not argv:
        return 0
    cmd = argv[0]

    if cmd == "sync" and "--dry-run" in argv:
        target = next((a for a in argv[1:] if not a.startswith("-")), None)
        drift = bool(target) and (Path(target) / ".stub_drift").exists()
        print("DRIFT" if drift else "CLEAN")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
