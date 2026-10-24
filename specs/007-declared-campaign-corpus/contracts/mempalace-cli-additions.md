# Contract: mempalace CLI additions (`~/src/Mempalace`, `kostadis-dev`)

Three additions mneme depends on (research R1, R3, R4). They ship in mempalace first, then
the hypostasis pin is bumped. All take the global `--palace P` before the subcommand
(`runner.py:199-202`).

## 1. `mempalace mine DIR --files-from FILE [--wing W] [--dry-run] [--skips-json OUT]`

- `FILE` holds newline-separated paths, relative to `DIR` (or absolute under `DIR`). `-`
  means stdin.
- Passes the resolved list as `miner.mine(files=…)` (`miner.py:2362-2374`). `scan_project`
  is not called, so ignore files and `SKIP_DIRS` do not apply.
- `exclude_patterns` from `DIR/mempalace.yaml` still apply to pre-scanned files
  (`miner.py:2460`). mneme renders none for corpus campaigns.
- mneme passes resolved targets, never symlinks (mempalace opens with `O_NOFOLLOW`).
- A listed file is re-mined only if mempalace's already-mined check (source_file + mtime) passes it; mneme forgets a file first when its content hash changed, so a same-mtime edit is never skipped.
- A listed path that is missing, a symlink, not a regular file, or has an extension outside
  `READABLE_EXTENSIONS` is reported on the existing skip channel (`SKIP: <rel> (<reason>)`,
  parsed by `mine_report.parse_skips`). It is never silently dropped. mneme does NOT use that
  text to decide what was skipped for corpus mining; see `--skips-json` below.
- **`--skips-json OUT`** (GM decision 2026-10-24: mneme must stop guessing which files
  mempalace skipped from human-readable text). Valid only with `--files-from`. After the run,
  and on a partial failure too (best effort), `OUT` holds a JSON array with one object per
  listed file that was not (fully) mined:
  `{"path": str (as listed, relative to DIR, POSIX), "reason": str, "detail": str}`.
  Codes include `missing`, `symlink`, `not_regular`, `unsupported_ext`, `outside_dir`,
  `too_large`, `stat_error`, `chunk_cap`, and possibly `purge_skipped`. mneme treats any
  unknown code as a skip too. Text output is unchanged. `mempalace mine --help` lists
  `--skips-json`; mneme's `supports_corpus()` requires it, so a binary without it is refused
  as too old, naming the flag. If `OUT` is missing or unparseable after a run, the skip set
  is unknown: mneme records none of that kind's files as mined and warns.
- `--files-from` is mutually exclusive with `--include-ignored` and `--no-gitignore`.

## 2. `mempalace sources [--wing W] --json`

- Read-only. It prints a JSON array, one object per distinct `(wing, source_file)`:
  `{"wing": str, "source_file": str (absolute), "source_mtime": float|null, "drawers": int}`.
- Implemented over `facet_counts("source_file", where=…)` where the backend supports it,
  otherwise `sync._iter_drawer_metadata` (`sync.py:313-330`).
- Exit non-zero, and print no JSON, if the store cannot be opened. mneme then reports
  `UNKNOWN`.

## 3. `mempalace forget --sources-from FILE [--wing W] [--apply]`

- Deletes the drawers whose `source_file` (absolute, or relative to cwd and resolved) is in
  `FILE`. With no `--apply` it is a dry run.
- Prints a report mneme parses: `Sources: N`, `Drawers: M` (to delete / deleted), and one
  `  <path>  (<count>)` line per source, all listed (not top-N).
- Exit non-zero on any failure. It never deletes outside the listed sources.
