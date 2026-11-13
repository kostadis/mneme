# Implementation Plan: Corpus Brief

**Branch**: `corpus-brief` | **Date**: 2026-11-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/009-corpus-brief/spec.md`

## Summary

Add an optional, GM-declared `brief:` to `.mneme/corpus.yaml`: the ordered load-now subset of
the corpus (today: the planning document). mneme validates it as part of the corpus, answers
`mneme corpus brief` / MCP `corpus_brief` with the brief files plus a per-kind summary map
(trust, counts, bytes, declared-searchable) resolved fresh, and refuses with stable codes
whenever it cannot answer. A GM-run `mneme corpus migrate-brief` previews, then appends, a
`brief:` block to existing corpora. Briefing consumers (first: `campaign-prep`, mytools#87)
load the brief and reach everything else by search.

The approach extends 007's single resolution path rather than adding a parallel one (research
R1, R3). The spike on this branch (739851f) is reworked task by task (R10).

## Technical Context

**Language/Version**: Python ≥3.11 (runs on the GM's 3.14 venv)

**Primary Dependencies**: typer (CLI), PyYAML, optional `mcp` (FastMCP server); hypostasis
config for campaign discovery. No new dependency.

**Storage**: files only. `corpus.yaml` (tracked, GM-authored) gains a key; nothing new is
stored.

**Testing**: pytest (`tests/unit`, `tests/integration`), 007's `corpus_world` fixture and stub
mempalace; typer `CliRunner`.

**Target Platform**: Linux, the GM's host; campaign sparse clones under hypostasis
`data_roots.campaigns`.

**Project Type**: CLI + MCP server (single Python package `mneme/`).

**Performance Goals**: a brief answer costs one 007 resolution (already per-request for
`corpus toc`) plus one `stat` per declared file. No palace query.

**Constraints**: the answer stays under a few KB regardless of corpus size (SC-007); the
migration never changes an existing byte of `corpus.yaml` (FR-019).

**Scale/Scope**: 4–5 campaigns, ≤ ~500 declared files each, a handful of kinds.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Silicon Truth** ✅ — Sizes and membership are measured on disk per request. "Searchable"
  is labelled as *declared*, not observed (FR-007a); the observed palace state stays with
  `mp status`, so the brief makes no claim it has not checked. The migration validates the
  bytes it is about to write with the readers' own parser before replacing the file.
- **II. Sovereign Identity** ✅ — Consumers ask for "the campaign's brief", a meaning. The
  paths are the campaign's own encoding, read from its declaration.
- **III. Intrinsic State** ✅ — The brief lives inside the campaign's `corpus.yaml` and moves
  with it. The answer is derived and never stored.
- **IV. Transient Viewer** ✅ — Nothing new to rebuild; the answer is derived per request.
- **V. One Authority** ✅ — The brief is a subset of the corpus, enforced (`brief-undeclared`),
  never a second list (R1). One resolution feeds the CLI and MCP and both the brief and the map
  (R3), so no answer pairs one declaration's brief with another's map. Converted skills stop
  holding hardcoded path lists, which removes a second authority from each.
- **VI. Federated** ✅ — Per campaign. `migrate-brief --all` is independent per campaign; one
  refusal neither wedges nor rolls back the others (FR-020).
- **VII. Logical Datasets** ✅ — The map is per kind (the logical dataset), not per backing
  file (R5).
- **VIII. Transform the Constraint** ✅ — "The skill must know which grounding docs matter
  without hardcoding them" is removed by moving that editorial decision into the declaration
  the skill already consults. The 200K-token problem disappears because grounding is searched,
  not loaded (spec Context).
- **IX. Observability** ✅ — `corpus check` reports the brief or its absence; a broken brief is
  a corpus finding visible in `mp status`. A missing brief is deliberately not a status to-do
  (Clarification Q3, FR-013a): not every campaign is prepped, and the refusing consumer names
  the fix (`migrate-brief`).

**Human checkpoint**: the brief's contents are an editorial precision decision, and the GM
makes it. `migrate-brief` proposes a default (`docs/planning.md`) and writes only what the GM
reviewed in the preview and then applied. No LLM output feeds the declaration.

**Result: PASS.** Complexity Tracking is empty.

### Post-design re-check (after Phase 1)

**Still PASS.** Two choices were re-checked:
- **A new consumer mode `brief`** (R8) could look like a parallel classification. It is the
  existing `MODES` vocabulary extended by one value, read by the same `compliance()`.
- **The migration writes `corpus.yaml`**, which 007 limited to `init` and the adopt-time kind
  move. It uses the same pattern as that move (parse to decide, targeted text edit, validate
  with the reader, atomic replace), is GM-invoked and preview-first, and only appends. FR-004 is
  amended in the spec to say so.

## Project Structure

### Documentation (this feature)

```text
specs/009-corpus-brief/
├── plan.md
├── research.md          # R1–R12
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── corpus-yaml-brief.md
│   ├── brief-json.md
│   ├── cli.md
│   └── consumer-obligations.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
mneme/corpus/
├── config.py        # `brief` top-level key; CorpusConfig.brief; structural findings
├── resolve.py       # brief-undeclared membership finding
├── api.py           # one fresh resolution → consult() + brief(); refusal codes
├── brief_migrate.py # NEW: migrate-brief preview/apply (text append + validate + atomic)
├── cli.py           # `corpus brief`, `corpus migrate-brief`; check line; init skeleton
└── consumers.py     # MODES += "brief"
mneme/mcp/server.py  # corpus_brief tool
mneme/recipes/
├── consumers.yaml                         # mode vocabulary only (rows change in mytools#87 work)
└── instructions/manage-mempalace.md       # consumer obligations 4–5

tests/
├── unit/test_corpus_brief_config.py       # shape + membership findings
├── unit/test_corpus_brief_answer.py       # api.brief: order, kinds, searchable, sizes, refusals
├── unit/test_brief_migrate.py             # preview/apply/refusals, byte preservation
├── unit/test_corpus_consumers.py          # brief mode compliant; pinned counts
└── integration/test_corpus_brief_readers.py  # CLI == MCP, freshness, stale-copy refusal, adopt keeps brief
```

**Structure Decision**: Single package, extending `mneme/corpus/` beside 007's modules. The
migration gets its own module because it is the only write path; the readers stay read-only.

## Complexity Tracking

No violations.
