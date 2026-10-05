#!/usr/bin/env python3
"""A recording stub for the `mempalace` CLI (test double).

Records each invocation (argv) as a line in ``$MNEME_STUB_LOG`` so orchestration can
be tested without a real palace — and so "no re-embed on restore" is assertable (a
`mine` line in the log means embeddings were (re)computed; restore must add none).

Palace resolution: `--palace <path>` arg or ``$MEMPALACE_PALACE_PATH`` env.

- ``mine <path> [--palace P] [--dry-run]`` → exit 0; on a real (non-dry) run, create a
  fake turbovec store at ``P/turbovec/mempalace_drawers/{store.sqlite3,index.tvim}``.
  ``$MNEME_STUB_MINE_SKIPS`` (GH #31): newline-separated lines the mine prints; a line
  starting ``out:`` goes to stdout (the older mempalace), anything else to stderr.
- ``status [--palace P]`` → exit 0, prints ``ok``.
- ``[--palace P] sync <path> --dry-run`` → the REAL report format (GH #22). Counts via
  ``$MNEME_STUB_SYNC``: ``"<missing>,<gitignored>[,<oos>]"`` (default ``0,0``),
  ``rc1`` (error, rc 1),
  ``nopalace`` ("No palace found", rc 0), or ``garbage``.
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


def _write_store(path: Path) -> None:
    """A real tiny turbovec-like store: `meta(dim=384)` (the onnx default) so the GH #26 guard
    can read it."""
    import sqlite3

    path.unlink(missing_ok=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)")
    con.execute("INSERT INTO meta VALUES('dim','384')")
    con.commit()
    con.close()


def main() -> int:
    argv = sys.argv[1:]
    log = os.environ.get("MNEME_STUB_LOG")
    if log:
        with open(log, "a") as fh:
            fh.write(" ".join(argv) + "\n")

    sub, subargs, palace = _parse(argv)

    if sub == "mine":
        for line in os.environ.get("MNEME_STUB_MINE_SKIPS", "").split("\n"):
            if line.startswith("out:"):
                print(line[4:], flush=True)
            elif line:
                print(line, file=sys.stderr, flush=True)

    if sub == "mine" and "--dry-run" not in subargs:
        if palace:
            for coll in ("mempalace_drawers", "mempalace_closets"):
                d = Path(palace) / "turbovec" / coll
                d.mkdir(parents=True, exist_ok=True)
                _write_store(d / "store.sqlite3")
                (d / "index.tvim").write_text("stub-index\n")
            (Path(palace) / "knowledge_graph.sqlite3").write_text("stub-kg\n")
        return 0

    if sub == "status":
        print("ok")
        return 0

    if sub == "sync" and "--dry-run" in subargs:
        mode = os.environ.get("MNEME_STUB_SYNC", "0,0")
        if mode == "rc1":
            print("sync exploded", file=sys.stderr)
            return 1
        if mode == "nopalace":
            print(f"No palace found at {palace}")
            return 0
        if mode == "garbage":
            print("DRIFT")
            return 0
        counts = [int(x) for x in mode.split(",")]
        missing, gitignored, oos = counts[0], counts[1], (counts[2] if len(counts) > 2 else 0)
        print("  === MemPalace Sync (dry run) ===")
        print(f"  Scanned:        {missing + gitignored + 5}")
        print("  Kept:           5")
        print(f"  Gitignored:     {gitignored}  (would remove)")
        print(f"  Missing:        {missing}  (would remove)")
        print("  No source:      0  (kept)")
        print(f"  Out of scope:   {oos}  (kept)")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
