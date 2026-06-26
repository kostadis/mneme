#!/usr/bin/env python3
"""A recording stub for the `mempalace` CLI (test double).

Records each invocation (argv) as a line in ``$MNEME_STUB_LOG`` so orchestration can
be tested without a real palace — and so "no re-embed on restore" is assertable (a
`mine` line in the log means embeddings were (re)computed; restore must add none).

Palace resolution: `--palace <path>` arg or ``$MEMPALACE_PALACE_PATH`` env.

- ``mine <path> [--palace P] [--dry-run]`` → exit 0; on a real (non-dry) run, create a
  fake turbovec store at ``P/turbovec/mempalace_drawers/{store.sqlite3,index.tvim}``.
- ``status [--palace P]`` → exit 0, prints ``ok``.
- ``sync <path> --dry-run`` → ``DRIFT`` if ``<path>/.stub_drift`` exists, else ``CLEAN``.
- ``split ...`` → exit 0.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _parse(argv: list[str]) -> tuple[str | None, list[str], str | None]:
    """Split `[--palace P] [--version] SUBCMD [subargs]` → (subcommand, subargs, palace).

    `--palace` is a GLOBAL option (before the subcommand), as in the real mempalace CLI."""
    palace = os.environ.get("MEMPALACE_PALACE_PATH")
    rest: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--palace" and i + 1 < len(argv):
            palace = argv[i + 1]
            i += 2
            continue
        if a in ("--version", "-h", "--help"):
            i += 1
            continue
        rest.append(a)
        i += 1
    sub = rest[0] if rest else None
    return sub, rest[1:], palace


def main() -> int:
    argv = sys.argv[1:]
    log = os.environ.get("MNEME_STUB_LOG")
    if log:
        with open(log, "a") as fh:
            fh.write(" ".join(argv) + "\n")

    sub, subargs, palace = _parse(argv)

    if sub == "mine" and "--dry-run" not in subargs:
        if palace:
            for coll in ("mempalace_drawers", "mempalace_closets"):
                d = Path(palace) / "turbovec" / coll
                d.mkdir(parents=True, exist_ok=True)
                (d / "store.sqlite3").write_text("stub-bindings\n")
                (d / "index.tvim").write_text("stub-index\n")
            (Path(palace) / "knowledge_graph.sqlite3").write_text("stub-kg\n")
        return 0

    if sub == "status":
        print("ok")
        return 0

    if sub == "sync" and "--dry-run" in subargs:
        target = next((a for a in subargs if not a.startswith("-")), None)
        drift = bool(target) and (Path(target) / ".stub_drift").exists()
        print("DRIFT" if drift else "CLEAN")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
