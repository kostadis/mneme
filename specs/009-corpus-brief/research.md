# Research: Corpus Brief (009)

Every decision below is checked against the 007 code it extends (`mneme/corpus/{config,
resolve,api,toc,cli,consumers}.py`, `mneme/mcp/server.py`) and against the WIP spike on
branch `corpus-brief` (commit 739851f), which is exploratory input only.

## R1. Where `brief:` is validated

- **Decision**: Two layers, mirroring 007. `config.py` validates shape (a list of strings,
  path rules, no duplicates, not empty) and stores `CorpusConfig.brief` as an ordered tuple.
  `resolve.py` checks membership against the resolved kinds and adds a `brief-undeclared`
  finding for an entry that is neither a resolved file nor a declared-but-absent
  (`not_materialized` / `missing`) path of any kind.
- **Rationale**: This is the same split 007 uses ("structural half" in config, "disk half"
  in resolve). Membership needs `dirs` expanded, which only resolve does. As a corpus finding,
  `brief-undeclared` makes the whole corpus invalid (FR-002), so `corpus check`, `corpus toc`
  and `mp status` all see it, with no new reporting path.
- **Alternatives considered**: (a) Check membership only inside the brief command. Rejected:
  a broken brief would pass `corpus check` and surface only when a skill runs, which is
  Opacity (IX). (b) A separate `brief.yaml`. Rejected: a second hand-written list beside the
  corpus is the split-brain (V) that FR-002 forbids.

## R2. A brief file absent on this checkout

- **Decision**: Not a corpus finding. The brief answer refuses with `brief-unavailable`,
  naming each absent entry.
- **Rationale**: 007 made validity independent of the sparse checkout (R7 there:
  `not_materialized` is not an error). The brief inherits that. Refusing at answer time keeps
  FR-010's "no partial brief" without making a sparse host's corpus invalid.
- **Alternatives considered**: Returning a partial brief with an `absent` list. Rejected by
  the spec (FR-010/011: no substitute answer).

## R3. One resolution, two readers, no second parse

- **Decision**: Factor 007's `fresh()` so that it yields `(cfg, resolved, toc_doc)`.
  `consult()` (the existing per-kind reader) and the new `brief()` both call it, so the
  `corpus.yaml` bytes are read and validated once per request. The CLI `mneme corpus brief`
  and the MCP `corpus_brief` tool both call `api.brief()` (FR-008).
- **Rationale**: 007's rule is that the CLI and MCP answer through one function (`consult`)
  so the readers cannot diverge. The spike called `load()` a second time after `consult()`,
  which reads the file twice: a hand-edit between the two reads could pair one declaration's
  brief with another declaration's TOC.
- **Alternatives considered**: Adding `brief` to the TOC document. Rejected: the TOC snapshot
  (`corpus.toc.json`) and its `toc-json` contract are 007 schema 1. Changing them would make
  every existing snapshot `toc-stale` and widen the change. The brief answer is its own
  document (contract `brief-json.md`).

## R4. What "searchable" means per kind

- **Decision**: From the declaration and resolution only (Clarification Q1). For each kind,
  `searchable_files` = the kind's resolved files with `minable: true` and a non-null
  `mined_as` (mined under this kind's wing or, for a shared file, another kind's), and
  `searchable` = `searchable_files > 0`. Both come from the existing `ResolvedFile` fields.
  No palace query.
- **Rationale**: `minable` (readable extension, not a skip name) and `mined_as` are exactly
  what `mp refresh` uses to decide what is mined, so "searchable" says what refresh will
  index. Whether it has indexed it yet is `mp status`'s `corpus` row (FR-007a).
- **Alternatives considered**: A boolean per kind only. Rejected: a kind of PDFs or
  skip-named files is declared but not searchable, and a count makes that visible without a
  file listing.

## R5. Map granularity and size

- **Decision**: One summary per kind: `standard`, `trust`, `files` (count), `bytes` (sum of
  the declared paths' sizes), `searchable`, `searchable_files` (Clarification Q2). No
  per-file listing; the consumer asks `corpus toc --kind K` / `corpus_files` for that.
- **Rationale**: Out of the Abyss declares ~470 files. A per-file map is ~40–60 KB of JSON,
  which a skill reading Bash output gets truncated (seen in this session). The per-kind map is
  well under 2 KB (SC-007).

## R6. Sizes

- **Decision**: `bytes` = `os.stat(<campaign>/<declared path>).st_size`, following a symlink
  to its target, which is what a consumer opening the declared path reads. Measured at answer
  time, never cached.
- **Rationale**: FR-006 (fresh). The resolution already hashed every file, so the stat cost
  is negligible against it.

## R7. Refusal codes

- **Decision**: Reuse 007's `not-declared` (no corpus) and `invalid` (any finding, including
  `brief-undeclared`). Add `no-brief` and `brief-unavailable`. The CLI exits with
  `EXIT_RUNTIME` and prints `error: <detail>` plus findings on stderr, exactly as `corpus toc`
  does. MCP returns `{campaign, error, detail}`, as `corpus_files` does. Discovery errors
  (unknown campaign, foreign owner, store-alias clash) propagate unchanged, which is the
  stale-copy guard (Story 3, scenario 5).
- **Rationale**: One vocabulary across `toc`, `corpus_files` and `brief`; consumers already
  handle the first two.

## R8. Consumer inventory mode

- **Decision**: Add `brief` to `consumers.MODES` as a compliant mode (FR-014). A briefing
  consumer's row is `mode: brief`, `kinds:` = the kinds its brief draws from. The pinned
  mode-count test changes accordingly.
- **Rationale**: `toc` means "reads one kind's file list". A briefing consumer reads a
  GM-chosen subset plus a summary, which is a different obligation, and status should say so.
- **Alternatives considered**: Reuse `toc` with a note. Rejected: the mode is what
  `consumers --noncompliant` and status count, and `note` is free text no code reads.

## R9. Who writes `brief:`

- **Decision**: Only the GM (FR-004). `mneme corpus init`'s skeleton gains a commented
  `# brief:` block naming `docs/planning.md` as the example. `mp adopt`/`publish`, which may
  rewrite `kinds:` (mneme#71), carry `brief:` through verbatim and never add, drop or reorder
  entries.
- **Rationale**: The brief is an editorial precision decision (Authority & the Human
  Checkpoint). The adopt rewrite already parses and re-emits `corpus.yaml`; it must not lose
  an unknown-to-it key.
- **Follow-up for the plan**: verify the adopt/publish rewrite path preserves top-level keys
  it does not manage; add a test.

## R10. What the spike got right and wrong

- **Kept**: the config/resolve split, the `brief-undeclared` finding, the refusal codes, the
  CLI and MCP surfaces.
- **Changed**: per-file map → per-kind summary (R5); double `load()` → one resolution (R3);
  `searchable` added (R4); `check` output gains brief bytes (FR-013); `consumers` mode
  `brief` (R8); skeleton (R9); no new tests in the spike → contract and integration tests.
- **Disposition**: the spike commit stays on the branch history for reference. The
  implementation reworks it task by task rather than reverting and retyping it.

## R11. The brief migration (GM request, User Story 5)

- **Decision**: `mneme corpus migrate-brief [CAMPAIGN] [--all] [--file PATH ...] [--apply]`.
  Preview by default; `--apply` writes. `--file` repeats in the GM's order and defaults to
  `docs/planning.md`. It is a targeted text edit, following `corpus_guard.migrate_shadowed`
  (the adopt-time `campaign_kinds:` → `kinds:` move): read the bytes, refuse if a top-level
  `brief` key exists (detected by parsing, so any form counts), append
  `\nbrief:\n  - <path>\n…` (with a newline inserted first if the file does not end in one),
  validate the new bytes with `config.parse` and a fresh resolution against them, then
  `atomic` replace. Nothing is rewritten through a YAML dump, so comments and order survive
  (FR-019).
- **Rationale**: The proposal is shown in full before anything is written. That preview is
  the human checkpoint for an editorial (precision) decision, so FR-004's "GM declares it"
  holds. Reusing the adopt edit's approach (parse to decide, text-edit to write, validate the
  result with the reader's own code) means the migration cannot write a file the readers
  would refuse.
- **`--all`**: iterates `discover(entity)`'s owned campaigns. Each campaign is independent
  (FR-020). Exit 0 when every campaign previewed or applied cleanly, non-zero when any
  refused; a refusal is printed per campaign and never rolls another back.
- **Alternatives considered**: (a) A standalone script outside the CLI. Rejected: it would
  have to re-implement campaign discovery, ownership and the store-alias guard, which the
  `mneme corpus` group already enforces through `--dir`/name resolution. (b) A YAML
  round-trip write. Rejected: it drops comments and reorders keys, and the GM's
  `corpus.yaml` files are commented. (c) Letting the migration replace an existing brief.
  Rejected: editing an existing editorial decision is a hand edit, not a migration.

## R12. Adopt must preserve `brief:`

- **Decision**: No code change expected. `migrate_shadowed` is a targeted edit of
  `campaign_kinds:`/`kinds:` that leaves other top-level keys untouched, and the rewritten
  bytes are re-validated by `config.parse`, which now knows `brief`. Add a regression test:
  a corpus with `brief:` and a shadowed campaign kind, adopted, keeps `brief:` byte-for-byte.
