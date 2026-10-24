# Contract: CLI surface (delta)

All commands take the existing `--config/-c` and `--dir/-d`.

## New group: `mneme corpus`

| Command | Effect | Writes |
|---|---|---|
| `mneme corpus init CAMPAIGN` | Skeleton `.mneme/corpus.yaml` listing the standard kinds as comments, no paths. Refuses if the file exists. | `corpus.yaml` (new only) |
| `mneme corpus check CAMPAIGN` | Validate the configuration and print the resolution per kind (files, not-materialized, missing, findings). Exit 0 iff valid. | nothing |
| `mneme corpus toc CAMPAIGN [--kind K] [--json] [--write]` | Resolve the corpus **now** (never from the snapshot) and print it, or one kind. Exit non-zero if the configuration is invalid. `--write` also refreshes the snapshot file. This is the consumer entry point (FR-012). | snapshot with `--write` only |
| `mneme corpus current CAMPAIGN` | Files the current palace holds, from `mempalace sources`, grouped by wing; "no palace" when there is none. Read-only input for writing `corpus.yaml` (FR-020). | nothing |
| `mneme corpus consumers [--noncompliant]` | The consumer inventory with compliance per consumer. | nothing |

## Changed `mneme mp` commands (corpus campaigns only; the wing model is unchanged)

| Command | Change |
|---|---|
| `mp render` / `mp faces` | Derive wings from kinds. Write the root `mempalace.yaml` (palace + rooms) and the TOC, and append the TOC to `.gitignore`. Remove per-wing renders left from the wing model. Write `canon_wings`/`index_wings` into `config.yaml`; no transitional `canon_wing` (R8, GM decision: the CG change ships first). |
| `mp refresh` | Per kind: `mempalace --palace P mine <root> --wing <kind> --files-from <tmp>`, covering minable files whose `mined_as` is that kind. Each run goes through the embedder guard first, as today. Update `mneme-corpus-mined.json` after each successful kind. `--dry-run` prints the per-kind file lists. |
| `mp status` | New `corpus` row (states in `data-model.md`) and a fleet-level `consumers` row (non-compliant count, `mneme corpus consumers --noncompliant`). For corpus campaigns the `index` row comes from the corpus comparison, not `sync --dry-run`. |
| `mp prune` | Deletion set = `undeclared ∪ (missing − not_materialized)`, computed by mneme, previewed with per-file counts, bound by `--confirm --expect N`, backed up, then `mempalace forget --sources-from <tmp> --apply`, then re-verified with `sources` (R4). Refuses when the set includes drawers from a former `authoritative` wing unless `--include-former-canon <wing>` names it; a store rebuilt or first built from the corpus records no former wings (migration is `mp regenerate --confirm`, a fresh rebuild). |
| `mp bringup` | When `corpus.yaml` exists, provision and first-mine from the corpus. Otherwise unchanged. |

## `mneme mp mcp`

New tool: `corpus_files(campaign, kind)` → the kind's files, resolved fresh on every call (same logic as
`mneme corpus toc`). It returns an explicit error for an invalid configuration or an undeclared kind.