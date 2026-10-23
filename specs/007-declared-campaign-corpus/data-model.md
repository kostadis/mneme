# Data Model: Declared Campaign Corpus

Authority vs derived, as in 002/005/006. One authority per fact. Everything marked
*derived* is regenerated from an authority, stamped, and never hand-edited.

## Entities

### KindDef (recipe, mneme-owned, versioned)

The standard kinds, from `mneme/recipes/mempalace.recipe.v3.yaml` → `kinds:`.

| Field | Type | Notes |
|---|---|---|
| `name` | str | Lower-case slug: `npcs`, `summaries`, `party`, `grounding`, `prep`. It becomes the wing name. |
| `default_trust` | `TRUST_LEVELS` | `authoritative` \| `accelerator` \| `reference` (`models.py`) |
| `rooms_hint` | tuple[str] | Room scaffold for the derived root `mempalace.yaml` |

### CorpusConfig (authority, `<campaign>/.mneme/corpus.yaml`, tracked)

| Field | Type | Notes |
|---|---|---|
| `campaign` | str | Must equal the mempalace authority's `campaign` |
| `kinds` | map[name → KindDecl] | Standard kinds, by their standard name |
| `campaign_kinds` | map[name → KindDecl] | Campaign-defined kinds. This is a separate key, so a typo under `kinds:` is caught (FR-003a). |
| `source_sha256` | — | Not stored. Computed as sha256 of the file bytes (the TOC stamp). |

### KindDecl

| Field | Type | Notes |
|---|---|---|
| `dirs` | list[relpath] | Each one admits its contents recursively |
| `files` | list[relpath] | Exact files |
| `trust` | `TRUST_LEVELS`, optional | Optional for a standard kind (defaults to `default_trust`); **required** for a campaign kind (FR-004) |
| `mined_as` | bool, optional | Only meaningful when a file is reachable from more than one kind (research R2) |

A KindDecl may set both `dirs` and `files`. It must set at least one, or it is
`invalid: empty-declaration`.

### ResolvedCorpus (computed in memory; never stored)

For each declared kind: the files it resolves to on this checkout, each classified as one of:

- **minable**: a regular file that exists (or a symlink resolving to one inside the campaign;
  then the resolved target is what is mined), and has an extension mempalace
  reads (`READABLE_EXTENSIONS`, `miner.py:140-181`).
- **non-minable**: exists but has a non-readable extension (e.g. `.pdf`). Listed in the TOC
  with `minable: false`, so it is never reported as unmined.
- **not_materialized**: tracked but skip-worktree (sparse, research R7).
- **missing**: declared path absent and not tracked.

A file's **mining kind** is its single declaring kind, or the kind whose declaration sets
`mined_as: true` (R2).

### CorpusTOC (derived, `<campaign>/.mneme/corpus.toc.json`, host-local, gitignored)

The published resolution of the corpus. The schema is in `contracts/toc-json.md`. It is
stamped with `corpus_sha256` + `recipe_version`. Every consumer of campaign files reads this
file (FR-021).

### CorpusMinedRecord (derived, `<store>/mneme-corpus-mined.json`)

`{schema, campaign, mined_at, corpus_sha256, files: {relpath: {kind, sha256, target}}}`, where
`target` is the resolved path actually mined (equal to `relpath` unless it is a symlink). It is written
after each successful corpus mine, per kind, and merged. It has the store's lifecycle:
`regenerate` wipes it (R3). It is the only place "what content was embedded" is recorded,
because mempalace keeps no content hash.

### SourceRecord (observed, from `mempalace sources --json`)

`{wing, source_file (absolute), source_mtime, drawers}`. mneme converts `source_file` to a
campaign-relative path. A source outside the campaign root counts as `out_of_scope`, as today.

### Consumer (recipe, mneme-owned, `mneme/recipes/consumers.yaml`, GM-maintained)

| Field | Type | Notes |
|---|---|---|
| `name` | str | e.g. `cg.prep`, `skill.campaign-prep`, `skill.campaign-recall` |
| `repo` | str | `CampaignGenerator`, `~/.claude/skills`, `gm-assistant`, … |
| `entry` | str | `file:line` evidence |
| `kinds` | list[kind] | Kinds it reads |
| `mode` | `palace` \| `toc` \| `independent` \| `partial` | `palace`/`toc` = compliant; `independent` = non-compliant; `partial` = some kinds via the TOC (e.g. CG search during the R8 transition) |
| `issue` | str, optional | Follow-up issue tracking its conversion |

## Corpus finding states (status `corpus` row, FR-015)

```
                       ┌─────────────┐
 no corpus.yaml ──────▶│ UNDECLARED  │  owed work; wing model still mines (FR-019)
                       └─────────────┘
 corpus.yaml present:
   parse/validate fails ─────────────▶ INVALID   (dual-authority, unknown-kind, shadowed-kind,
                                                  ambiguous-mining-kind, gitignored, symlink,
                                                  empty-declaration, missing trust)
   declared path absent, untracked ──▶ MISSING   (config edit)
   sources/record unreadable ────────▶ UNKNOWN   (never OK, FR-017)
   otherwise compare sets:
     sources − TOC ──────────────────▶ UNDECLARED-DRAWERS  (mp prune)
     TOC(minable) − sources ─────────▶ UNMINED   (mp refresh)
     sha256(TOC) ≠ sha256(record) ───▶ STALE     (mp refresh)
     TOC stamp ≠ corpus.yaml bytes ──▶ TOC-STALE (mp render)
   none of the above ────────────────▶ OK
```

These are not mutually exclusive. The row lists every finding with counts and files. It is
OK only when there are none (FR-017). `not_materialized` is informational, never a finding.

## Validation rules

1. `campaign` matches the mempalace authority's.
2. A name under `kinds:` must be a standard kind; a name under `campaign_kinds:` must
   **not** be one. If a recipe upgrade adds a standard kind with the same name as an existing
   campaign kind, the result is `invalid: shadowed-kind`, reported and never merged.
3. Paths are relative and normalized, and must not escape the campaign root (`..`).
4. Declared paths must not be gitignored. mneme asks `git check-ignore`, which also covers
   `.git/info/exclude`. mempalace does not read that file, but consumers using git do.
5. A declared path, or a file inside a declared dir, may be a symlink only if it resolves to a
   regular file inside the campaign. mneme mines the resolved target, since mempalace opens files
   with `O_NOFOLLOW`. Anything else is `invalid: symlink-outside` / `symlink-not-file`.
6. A file reachable from more than one kind needs exactly one `mined_as: true` among them,
   and the trust levels must agree. If they differ, the result is `invalid: trust-conflict`.
7. When `corpus.yaml` exists, `.mneme/mempalace.yaml` must not carry `wings:` or
   `extra_exclusions:` (`invalid: dual-authority`).
8. A declaration that resolves to zero files in total is `invalid: empty-corpus`.
