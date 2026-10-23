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
- ``mine DIR --files-from F --wing W`` (feature 007) → unless ``--dry-run``, appends
  ``(W, abs path)`` for each path in F (relative to DIR, or absolute; ``-`` = stdin) to the
  JSON state file ``$MNEME_STUB_SOURCES_STATE``. Like real mempalace, a source already in the
  state is skipped, whatever its wing. A missing path prints
  ``SKIP: <rel> (not a regular file)``.
- ``sources [--wing W] --json`` → a JSON array of ``{wing, source_file, source_mtime, drawers}``
  from that state (``[]`` without one). ``$MNEME_STUB_SOURCES=rc1`` exits 1, ``garbage`` prints
  non-JSON.
- ``forget --sources-from F [--wing W] [--apply]`` → the contract report (``Sources: N``,
  ``Drawers: M``, one ``  <path>  (<count>)`` line per source). ``--apply`` also removes those
  sources from the state. ``$MNEME_STUB_FORGET=rc1`` exits 1.
- ``--help`` / ``mine --help`` → verb list / mine usage naming ``--files-from``; with
  ``$MNEME_STUB_OLD`` set, the pre-007 CLI without them.
- ``status [--palace P]`` → exit 0, prints ``ok``.
- ``[--palace P] sync <path> --dry-run`` → the REAL report format (GH #22). Counts via
  ``$MNEME_STUB_SYNC``: ``"<missing>,<gitignored>[,<oos>]"`` (default ``0,0``),
  ``rc1`` (error, rc 1),
  ``nopalace`` ("No palace found", rc 0), or ``garbage``.
- ``[--palace P] sync <path> [--root R ...] --apply`` → the "removed" report form; logged.
  With ``$MNEME_STUB_APPLY_STATE`` (a file path) the apply writes it, and any later dry-run
  reports zero missing/gitignored (out-of-scope kept) — the post-prune check. Without it the
  counts never change (a prune that did not take). ``$MNEME_STUB_SYNC`` ``applyrc1`` makes
  the apply exit 1.
- ``split ...`` → exit 0.
"""

from __future__ import annotations

import json
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


def _opt(args: list[str], flag: str) -> str | None:
    return args[args.index(flag) + 1] if flag in args and args.index(flag) + 1 < len(args) else None


def _state_path() -> Path | None:
    st = os.environ.get("MNEME_STUB_SOURCES_STATE")
    return Path(st) if st else None


def _load_state() -> list[dict]:
    st = _state_path()
    if st is None or not st.exists():
        return []
    return json.loads(st.read_text())


def _save_state(rows: list[dict]) -> None:
    st = _state_path()
    if st is not None:
        st.write_text(json.dumps(rows))


def _read_list(spec: str) -> list[str]:
    text = sys.stdin.read() if spec == "-" else Path(spec).read_text()
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _mine_files(dir_: str, subargs: list[str]) -> None:
    wing = _opt(subargs, "--wing") or "stub"
    rows = _load_state()
    have = {r["source_file"] for r in rows}
    for rel in _read_list(_opt(subargs, "--files-from") or "-"):
        p = Path(rel) if os.path.isabs(rel) else Path(dir_) / rel
        if not p.is_file() or p.is_symlink():
            print(f"SKIP: {rel} (not a regular file)", file=sys.stderr, flush=True)
            continue
        ab = str(p.resolve())
        if ab in have:
            continue
        have.add(ab)
        rows.append(
            {"wing": wing, "source_file": ab, "source_mtime": p.stat().st_mtime, "drawers": 1}
        )
    _save_state(rows)


def _sources(subargs: list[str]) -> int:
    mode = os.environ.get("MNEME_STUB_SOURCES", "")
    if mode == "rc1":
        print("sources exploded", file=sys.stderr)
        return 1
    if mode == "garbage":
        print("not json")
        return 0
    wing = _opt(subargs, "--wing")
    print(json.dumps([r for r in _load_state() if wing is None or r["wing"] == wing]))
    return 0


def _forget(subargs: list[str]) -> int:
    if os.environ.get("MNEME_STUB_FORGET") == "rc1":
        print("forget exploded", file=sys.stderr)
        return 1
    wing = _opt(subargs, "--wing")
    listed = {str(Path(x).resolve()) for x in _read_list(_opt(subargs, "--sources-from") or "-")}
    rows = _load_state()
    hit = [r for r in rows if r["source_file"] in listed and (wing is None or r["wing"] == wing)]
    apply = "--apply" in subargs
    print(f"  === MemPalace Forget ({'apply' if apply else 'dry run'}) ===")
    print(f"  Sources: {len(hit)}")
    print(f"  Drawers: {sum(r['drawers'] for r in hit)}")
    for r in hit:
        print(f"    {r['source_file']}  ({r['drawers']})")
    if apply:
        _save_state([r for r in rows if r not in hit])
    return 0


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

    if "--help" in argv or "-h" in argv:  # `supports_corpus()` probe; $MNEME_STUB_OLD = old CLI
        old = bool(os.environ.get("MNEME_STUB_OLD"))
        if argv and argv[0] == "mine":
            print("usage: mempalace mine DIR" + ("" if old else " [--files-from FILE]"))
        else:
            print("{mine,status,sync,split}" if old else "{mine,sources,forget,status,sync,split}")
        return 0

    sub, subargs, palace = _parse(argv)

    if sub == "mine":
        for line in os.environ.get("MNEME_STUB_MINE_SKIPS", "").split("\n"):
            if line.startswith("out:"):
                print(line[4:], flush=True)
            elif line:
                print(line, file=sys.stderr, flush=True)

    if sub == "mine" and "--files-from" in subargs and "--dry-run" not in subargs and subargs:
        _mine_files(subargs[0], subargs)

    if sub == "sources":
        return _sources(subargs)

    if sub == "forget":
        return _forget(subargs)

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

    if sub == "sync" and ("--dry-run" in subargs or "--apply" in subargs):
        apply = "--apply" in subargs
        mode = os.environ.get("MNEME_STUB_SYNC", "0,0")
        state = os.environ.get("MNEME_STUB_APPLY_STATE")
        if apply and mode == "applyrc1":
            print("sync apply exploded", file=sys.stderr)
            return 1
        if mode == "applyrc1":
            mode = "0,0"
        done = bool(state) and Path(state).exists()
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
        if done and not apply:
            missing = gitignored = 0
        suffix = "(removed)" if apply else "(would remove)"
        print(f"  === MemPalace Sync ({'apply' if apply else 'dry run'}) ===")
        print(f"  Scanned:        {missing + gitignored + 5}")
        print("  Kept:           5")
        print(f"  Gitignored:     {gitignored}  {suffix}")
        print(f"  Missing:        {missing}  {suffix}")
        print("  No source:      0  (kept)")
        print(f"  Out of scope:   {oos}  (kept)")
        if missing + gitignored:
            label = "Top sources removed" if apply else "Top sources to remove"
            print(f"\n  {label}:")
            print(f"    /stub/gone.md  ({missing + gitignored})")
        if apply:
            print(f"\n  Removed {missing + gitignored} drawers, 0 closets.")
            if state:
                Path(state).write_text("applied\n")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
