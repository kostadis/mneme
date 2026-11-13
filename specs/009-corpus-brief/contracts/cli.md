# Contract: CLI surface (delta to 007 `contracts/cli.md`)

All commands take the existing `--config/-c` and `--dir/-d`.

| Command | Effect | Writes |
|---|---|---|
| `mneme corpus brief CAMPAIGN [--json]` | Resolve now and print the brief answer (`brief-json.md`). Human form: the brief files with kinds and sizes, the brief's total, then one line per kind (`trust`, `files`, `bytes`, `searchable_files`). Exit 0 on an answer; `EXIT_RUNTIME` with `error: <detail>` (and findings) on stderr on any refusal. | nothing |
| `mneme corpus migrate-brief (CAMPAIGN \| --all) [--file PATH]… [--apply]` | Propose adding `brief:` (default `docs/planning.md`; `--file` repeats in reading order). Preview: print, per campaign, the exact block to append, each file's kinds and bytes, and the total. With `--apply`: append that block (original bytes untouched), validated before an atomic replace. Refuses per campaign: `not-declared`, `invalid`, `brief-exists`, `brief-undeclared`, `brief-unavailable`. Exit 0 iff no campaign refused. | `corpus.yaml` with `--apply` only |

Changed commands:

| Command | Change |
|---|---|
| `mneme corpus check` | After the per-kind lines, prints `brief: N file(s), B bytes` or `brief: not declared`. A `brief-undeclared` finding fails the check like any other finding. |
| `mneme corpus init` | The skeleton gains a commented `# brief:` example (`# - docs/planning.md`). |
| `mneme corpus consumers` | Accepts and reports `mode: brief` as compliant. |
| `mneme mp status` | No new row. A missing brief is never outstanding work (FR-013a). A `brief-undeclared` finding appears in the existing `corpus` row, like every corpus finding. |

## `mneme mp mcp`

New tool `corpus_brief(campaign)` → the brief answer, from the same `api.brief()` the CLI
uses.
