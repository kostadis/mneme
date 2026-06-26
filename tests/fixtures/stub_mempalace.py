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


def _palace(argv: list[str]) -> str | None:
    if "--palace" in argv:
        i = argv.index("--palace")
        if i + 1 < len(argv):
            return argv[i + 1]
    return os.environ.get("MEMPALACE_PALACE_PATH")


def main() -> int:
    argv = sys.argv[1:]
    log = os.environ.get("MNEME_STUB_LOG")
    if log:
        with open(log, "a") as fh:
            fh.write(" ".join(argv) + "\n")

    if not argv:
        return 0
    cmd = argv[0]

    if cmd == "mine" and "--dry-run" not in argv:
        palace = _palace(argv)
        if palace:
            for coll in ("mempalace_drawers", "mempalace_closets"):
                d = Path(palace) / "turbovec" / coll
                d.mkdir(parents=True, exist_ok=True)
                (d / "store.sqlite3").write_text("stub-bindings\n")
                (d / "index.tvim").write_text("stub-index\n")
            (Path(palace) / "knowledge_graph.sqlite3").write_text("stub-kg\n")
        return 0

    if cmd == "status":
        print("ok")
        return 0

    if cmd == "sync" and "--dry-run" in argv:
        target = next((a for a in argv[1:] if not a.startswith("-")), None)
        drift = bool(target) and (Path(target) / ".stub_drift").exists()
        print("DRIFT" if drift else "CLEAN")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
