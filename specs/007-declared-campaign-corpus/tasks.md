---

description: "Task list for feature 007 — declared campaign corpus"
---

# Tasks: Declared Campaign Corpus

**Input**: Design documents from `specs/007-declared-campaign-corpus/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R10), data-model.md, contracts/, quickstart.md

**Tests**: Included. The plan's Testing section and quickstart scenarios 1–7 call for unit and
integration tests, and SC-004 requires a state-matrix test.

**Organization**: Grouped by user story (spec.md US1–US5) so each story can be built and
verified on its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US5 from spec.md
- **Who does it** (plan § Execution Model): every task goes to a **Sonnet 5.5 (`medium`)
  implementer** unless marked **(Opus)** (the orchestrator does it) or **(GM)** (a human
  checkpoint; no agent performs it).
- **Paths**: mneme tasks are relative to the worktree `~/src/mneme-007`. mempalace tasks are
  relative to the worktree `~/src/Mempalace-007` (created in T001).

## Rules every implementer brief carries

- Read the task's contract file(s) before writing code. The contracts are binding.
- mneme never imports mempalace. It calls the CLI through `mneme/mempalace/runner.py`
  (Principles VII/VIII).
- Unknown is never OK. Anything unverifiable is reported as unknown or unverified (FR-017).
- Never run pytest inside `git rebase --exec`.
- Match the surrounding code's style. Comments are sparse and cite the FR or research item
  they implement (as in `prune.py`, `conform.py`).

---

## Phase 1: Setup

**Purpose**: Workspaces and skeletons.

- [ ] T001 (Opus) Create the mempalace worktree: `git -C ~/src/Mempalace worktree add -b feat/corpus-cli ~/src/Mempalace-007 kostadis-dev`. Mempalace work always branches from and merges back to `kostadis-dev`, never `main` (`~/src/CLAUDE.md`).
- [ ] T002 [P] Create the empty package `mneme/corpus/__init__.py` with a module docstring naming feature 007 and stating that the corpus is campaign-level, not mempalace-specific (plan § Structure Decision).
- [ ] T003 [P] Create `mneme/recipes/mempalace.recipe.v3.yaml`. Copy v2's `mechanical:` and `scaffold:` unchanged, set `version: "3.0.0"`, and add a `kinds:` section: `npcs`, `summaries`, `party` and `grounding` with `default_trust: authoritative`, `prep` with `default_trust: reference`, each with a `rooms_hint` list. The header comment states that v3 adds kinds for declared-corpus campaigns and that wing-model campaigns keep working (research R6).

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: The mempalace CLI verbs, the runner, the corpus configuration, resolution and TOC.
Every user story needs these.

**⚠️ CRITICAL**: No user-story work starts until this phase is gated green.

### mempalace (`~/src/Mempalace-007`, contract `contracts/mempalace-cli-additions.md`)

- [ ] T004 Add `mine --files-from FILE` in `mempalace/cli/parser.py` and `mempalace/cli/cmd_mine.py`:
  - Read newline-separated paths (relative to DIR or absolute under it; `-` means stdin) and pass them as `miner.mine(files=…)` (`miner.py:2362`).
  - Report each missing, symlinked, non-regular or non-`READABLE_EXTENSIONS` path on the existing `SKIP: <rel> (<reason>)` channel.
  - Reject the flag combined with `--include-ignored` or `--no-gitignore`.
  - Tests go in the repo's existing mine tests.
- [ ] T005 Add `mempalace sources [--wing W] --json` (new `mempalace/cli/cmd_sources.py`, registered in `mempalace/cli/parser.py`):
  - Read-only. Print a JSON array of `{wing, source_file, source_mtime, drawers}`, one per distinct `(wing, source_file)`.
  - Use `facet_counts("source_file", …)` where the backend supports it, otherwise `sync._iter_drawer_metadata` (`sync.py:313-330`).
  - Exit non-zero with no JSON if the store cannot be opened.
  - Tests included.
- [ ] T006 Add `mempalace forget --sources-from FILE [--wing W] [--apply]` (new `mempalace/cli/cmd_forget.py`, registered in `mempalace/cli/parser.py`):
  - Dry run by default.
  - Delete only drawers whose `source_file` is listed, via the existing `delete(where={"source_file": …})` path.
  - Print `Sources: N`, `Drawers: M`, and one `  <path>  (<count>)` line per source, every source listed.
  - Exit non-zero on any failure.
  - Tests included.
- [ ] T007 (Opus) Gate the mempalace worktree: run its test suite and linter, read the diff against `contracts/mempalace-cli-additions.md`, then push `feat/corpus-cli` and open a PR into `kostadis-dev` via `mcp__github__create_pull_request`.
- [ ] T008 (GM) Review and merge the mempalace PR into `kostadis-dev`. mneme work that calls the new verbs is blocked until this lands.
- [ ] T009 Bump the mempalace pin in `hypostasis.example.yaml` (the `components.mempalace.pin` line) to the merged `kostadis-dev` commit, and update its comment to name feature 007's CLI additions. In the task report, tell the GM that each host's `~/.config/hypostasis/hypostasis.yaml` needs the same pin and a `hypostasis install`. This task does not touch host configs.

### mneme foundations

- [ ] T010 [P] Extend the test double `tests/fixtures/stub_mempalace.py` and update its docstring:
  - `mine … --files-from F --wing W` logs the argv and appends `(W, abs path)` pairs to a state file named by `$MNEME_STUB_SOURCES_STATE`.
  - `sources --json` prints that state as the contract's JSON. `$MNEME_STUB_SOURCES=rc1` exits 1, and `garbage` prints non-JSON.
  - `forget --sources-from F [--apply]` reports per the contract. With `--apply` it also removes those sources from the state file.
- [ ] T011 Add runner methods to `mneme/mempalace/runner.py`:
  - `mine_files(root, files, wing, palace, dry_run)` writes the list to a temp file and passes `--files-from`, then returns `MineResult` with skips parsed as today.
  - `sources(palace, wing=None) -> list[SourceRecord] | None` returns None (unknown) on rc≠0 or unparseable output, and never raises on a read.
  - `forget(sources, palace, apply)` returns a parsed report and raises `MempalaceError` on a failed apply.
  - Add `supports_corpus()`, which probes `mempalace --help` once for the three verbs.
  - Unit tests in `tests/unit/test_mp_runner_corpus.py`, against the stub.
- [ ] T012 [P] Add the recipe kinds:
  - Add `KindDef(name, default_trust, rooms_hint)` to `mneme/mempalace/models.py` and `kinds: tuple[KindDef, ...] = ()` to `Recipe`.
  - Parse `kinds:` in `mneme/mempalace/recipe.py` `_parse`. v1/v2 yield no kinds.
  - Tests in `tests/unit/test_mp_recipe_v3.py`: v3 loads five kinds with the ratified trusts, v2 loads none, and `current()` returns v3.
- [ ] T013 Implement `mneme/corpus/config.py`:
  - Dataclasses `CorpusConfig`, `KindDecl`, and `load(campaign_dir, recipe) -> CorpusConfig` raising `CorpusConfigError(findings)`.
  - Enforce `contracts/corpus-yaml.md` and data-model validation rules 1–3, 6 (the structural half: at most one `mined_as` per shared file, trust agreement) and 8, plus unknown-key rejection.
  - Error codes: `unknown-kind`, `shadowed-kind`, `missing-trust`, `empty-declaration`, `path-escape`, `trust-conflict`, `ambiguous-mining-kind`, `campaign-mismatch`.
  - `corpus_sha256` is the sha256 of the raw file bytes.
  - Table-driven tests in `tests/unit/test_corpus_config.py`, one case per code (quickstart scenario 5).
- [ ] T014 Implement `mneme/corpus/resolve.py`:
  - `resolve(cfg, campaign_dir, recipe) -> ResolvedCorpus` per data-model § ResolvedCorpus.
  - Expand `dirs` recursively and classify each file as minable, non-minable (extension outside mempalace's readable set; mirror the list in a constant with a comment citing `miner.py:140-181`), not_materialized (`git ls-files -t` reports `S`) or missing.
  - Emit `gitignored` (via `git check-ignore`) and `symlink` findings.
  - Assign each file its mining kind (R2).
  - Tests in `tests/unit/test_corpus_resolve.py`, using a temporary git repo with sparse/skip-worktree, a symlink, a gitignored file, a `.pdf` and a file shared across kinds.
- [ ] T015 Implement `mneme/corpus/toc.py` per `contracts/toc-json.md`:
  - `build(resolved, cfg, recipe) -> dict`, `write(campaign_dir, toc)` (atomic write, then append `.mneme/corpus.toc.json` to the campaign `.gitignore` if it is missing), `read(campaign_dir)`.
  - `verify(campaign_dir) -> TocCheck`, which returns missing, stale (corpus.yaml hash differs), invalid or ok.
  - `files_for(toc, kind)` distinguishes a kind that is not declared from one that is declared but empty.
  - Tests in `tests/unit/test_corpus_toc.py`.
- [ ] T016 Add the dual-authority check to `mneme/mempalace/authority.py`. When `.mneme/corpus.yaml` exists and `.mneme/mempalace.yaml` has `wings:` or `extra_exclusions:`, `load()` raises `AuthorityError` with `dual-authority`, naming both files (research R8, FR-001a). When `corpus.yaml` is present, `wings` may be absent; the existing "no wings" validation must not fire. Tests go in the existing authority unit tests.
- [ ] T017 (Opus) Gate Phase 2: `ruff check hypostasis mneme tests` and `pytest` in `~/src/mneme-007`. Read the diff against the contracts before Phase 3.

**Checkpoint**: the corpus can be loaded, validated, resolved and published as a TOC, and the runner can drive the new verbs.

---

## Phase 3: User Story 1 — The palace contains exactly the curated files (Priority: P1) 🎯 MVP

**Goal**: For a campaign with `corpus.yaml`, mining produces drawers from declared files only, with one wing per kind.

**Independent Test**: quickstart scenario 1. A fixture campaign with decoys, after render and refresh, has `sources` equal to the six declared files and nothing else.

- [ ] T018 [P] [US1] Implement `mneme/mempalace/corpus_record.py`, sibling of `mine_record.py`, same atomic-write and error style. It reads and writes `<store>/mneme-corpus-mined.json` (`{schema, campaign, mined_at, corpus_sha256, files: {relpath: {kind, sha256}}}`) and merges per kind after each successful kind mine (research R3).
- [ ] T019 [US1] Extend `mneme/mempalace/render.py` for corpus campaigns (`corpus.yaml` present):
  - Write the root `mempalace.yaml`, stamped, with `palace: <alias>` plus the union of rooms from the recipe kinds.
  - Write the TOC via `mneme/corpus/toc.py`.
  - Delete leftover per-wing `mempalace.yaml` and `.mempalaceignore` renders, but only files carrying mneme's stamp.
  - Write `config.yaml` `mempalace: {canon_wings, index_wings, canon_wing}`, with `canon_wing` set to the first authoritative kind in recipe order (R8).
  - Make `coherent()` and `render_faces()` cover the corpus artifacts.
  - The wing-model path is unchanged.
  - Tests in `tests/unit/test_mp_render_corpus.py`.
- [ ] T020 [US1] Extend `mneme/mempalace/refresh.py` for corpus campaigns:
  - Refuse with an unknown result if `runner.supports_corpus()` is false (plan Dependency 1).
  - Run the embedder guard, then for each kind call `runner.mine_files(campaign_dir, <minable files whose mined_as is this kind>, wing=kind)`.
  - Update the corpus record after each successful kind. Keep the GH #31 skip record.
  - `--dry-run` prints the per-kind file lists and mines nothing.
  - A failed kind stops the run and writes no clean record (mirror `_refresh_one`).
- [ ] T021 [US1] Make `mneme/mempalace/bringup.py` use the corpus path when `corpus.yaml` exists: provision, then corpus render, then per-kind first mine, then backup. Otherwise it is unchanged.
- [ ] T022 [P] [US1] Integration test `tests/integration/test_corpus_mining.py` for quickstart scenario 1:
  - Set up the fixture campaign in a temp git repo, with decoys `docs/campaign_state_draft.md`, `docs/party_draft.md`, `docs/reviews/x.md` and `summaries/raw.md`, using the stub.
  - Assert wings `npcs`/`summaries`/`grounding` and that no decoy is mined.
  - Assert that a new `docs/new_generated/y.md` adds nothing.
  - Assert that `mined_as` puts a shared `docs/party.md` in exactly one wing.
- [ ] T023 (Opus) Gate US1: ruff, pytest, diff review.

**Checkpoint**: MVP. Declared-corpus campaigns can no longer fail open.

---

## Phase 4: User Story 2 — Status proves the palace equals the corpus (Priority: P1)

**Goal**: `mp status` reports a corpus row with every finding, its remedy, and never a false OK. Prune deletes exactly the reviewed set.

**Independent Test**: quickstart scenarios 2 and 3.

- [ ] T024 [US2] Implement `mneme/corpus/compare.py`:
  - `compare(toc, sources, record, campaign_dir) -> CorpusFindings`, covering undeclared-drawers, unmined, stale (TOC sha differs from record sha), missing, invalid, toc-stale and unknown, per the data-model state diagram.
  - `not_materialized` is never a finding.
  - Sources outside the campaign root are `out_of_scope`.
  - OK only when there are no findings (FR-017).
- [ ] T025 [P] [US2] State-matrix unit tests `tests/unit/test_corpus_compare.py` (SC-004): one case per finding, combined findings, and "unknown when sources is None or the record is unreadable". Every non-matching case must be not-OK.
- [ ] T026 [US2] Wire into `mneme/mempalace/conform.py`:
  - In `_campaign_rows`, when `corpus.yaml` exists, add a `corpus` row (new `State` values as needed in `mneme/mempalace/models.py`) whose note lists each finding with counts, files (truncated past 10 with a count), and remedy (`mp prune` / `mp refresh` / edit `corpus.yaml` / `mp render`), per FR-015/016.
  - Replace the `index` row for corpus campaigns with one derived from the same comparison.
  - The wing-model path is untouched.
- [ ] T027 [US2] Extend `mneme/mempalace/prune.py` for corpus campaigns:
  - The deletion set is `undeclared ∪ (missing − not_materialized)`, computed by `compare.py`.
  - The preview lists every source with its drawer count. `--confirm --expect N` is bound to N drawers.
  - Back up first (unless `--no-backup`), apply `runner.forget(apply=True)`, then re-verify with `runner.sources()` and fail if any deleted source remains.
  - Not-materialized sources are never in the set (FR-018, R4, R7).
  - Unit tests in `tests/unit/test_mp_prune_corpus.py`.
- [ ] T028 [P] [US2] Integration test `tests/integration/test_corpus_status_prune.py` for quickstart scenarios 2 and 3: every row of the scenario-2 table, then the prune preview, confirm and re-verify flow, and the skip-worktree survivor.
- [ ] T029 (Opus) Gate US2: ruff, pytest, diff review.

**Checkpoint**: US1 + US2 make the palace provably exact.

---

## Phase 5: User Story 3 — Every consumer reads the same file list (Priority: P2)

**Goal**: Three equivalent TOC readers (file, CLI, MCP), all applying the consumer obligations in `contracts/toc-json.md`.

**Independent Test**: quickstart scenario 4.

- [ ] T030 [US3] Create `mneme/corpus/cli.py` with a Typer app and `check` plus `toc [--kind K] [--json] [--write]` (`contracts/cli.md`). `toc` applies verify steps 1–3 and exits non-zero on missing, stale or invalid. Register it in `mneme/cli.py` with `app.add_typer(corpus_app, name="corpus")`. Both take `--config` and `--dir` like `mneme mp`.
- [ ] T031 [P] [US3] Add an MCP tool `corpus_files(campaign: str, kind: str) -> dict` in `mneme/mcp/server.py`, beside `get_status`. It returns `{files}` or `{error: "toc-missing"|"toc-stale"|"invalid"|"not-declared", detail}`.
- [ ] T032 [P] [US3] Integration test `tests/integration/test_corpus_toc_readers.py` for quickstart scenario 4: the JSON file, `mneme corpus toc --json` and `corpus_files` return identical lists; all three refuse after `corpus.yaml` is edited; an undeclared kind gets "not declared", not `[]`.
- [ ] T033 [P] [US3] Add a "Declared corpus" section to `mneme/recipes/instructions/manage-mempalace.md`: the `corpus.yaml` shape, the TOC, the consumer obligations (read the TOC, refuse when stale), and `mined_as`. The `mneme mp mcp` server serves it.
- [ ] T034 (Opus) Gate US3: ruff, pytest, diff review.

---

## Phase 6: User Story 4 — Existing campaigns move to a declared corpus deliberately (Priority: P2)

**Goal**: Campaigns without a declaration are shown as owing one. The GM gets read-only input and a pathless skeleton. mneme never writes membership.

**Independent Test**: quickstart scenario 6, on a fixture first, then the live fleet.

- [ ] T035 [US4] Add `corpus current CAMPAIGN` (files the palace holds, from `runner.sources()`, grouped by wing; read-only) and `corpus init CAMPAIGN` (a skeleton `corpus.yaml` listing the standard kinds as comments, no paths; refuses if the file exists) to `mneme/corpus/cli.py` (FR-020, R10).
- [ ] T036 [US4] In `mneme/mempalace/conform.py`, a campaign with a mempalace authority but no `corpus.yaml` gets a `corpus` row `UNDECLARED (owed)` with the remedy `mneme corpus init`. Its other rows and wing-model mining are unaffected (FR-019).
- [ ] T037 [P] [US4] Integration test `tests/integration/test_corpus_migration.py`, using a wing-model fixture palace with a root wing:
  - Status shows undeclared-owed.
  - `corpus current` lists today's files.
  - After a `corpus.yaml` is written, render, then status shows the old extra drawers as `undeclared-drawers`, and nothing is deleted before the prune is confirmed.
- [ ] T038 (Opus) Gate US4: ruff, pytest, diff review.
- [ ] T039 (GM) Live migration, one campaign at a time (obelisk, toee, out-of-the-abyss):
  - The GM writes each `corpus.yaml` (`mneme corpus init` provides the skeleton).
  - Opus runs `mp render` and `mp status` and shows the prune preview.
  - The GM alone runs `mp prune --confirm --expect N`, then `mp refresh`, until `corpus: OK` (SC-003, SC-007).

---

## Phase 7: User Story 5 — See which consumers are not yet on the TOC (Priority: P3)

**Goal**: Status surfaces every non-compliant consumer from the GM-reviewed inventory.

**Independent Test**: quickstart scenario 7.

- [ ] T040 [US5] Implement `mneme/corpus/consumers.py`: load and validate `mneme/recipes/consumers.yaml` (`contracts/consumers-yaml.md`; unknown modes and unknown kinds are errors) and compute `compliant(c)` (palace/toc = yes, partial = partly, independent = no). Add `corpus consumers [--noncompliant]` to `mneme/corpus/cli.py`. Tests in `tests/unit/test_corpus_consumers.py`, including a test that the shipped file parses and contains 52 entries.
- [ ] T041 [US5] Add one fleet-level `consumers` row to `mneme/mempalace/conform.py` `report()`, with the non-compliant count and the command to list them (FR-024). Shown once, not per campaign.
- [ ] T042 (Opus, GM approves) Draft one follow-up issue per consumer repo: CampaignGenerator (including `documents[]`, `grounding_bundle.py` and `canon_wings`), `~/.claude/skills`, gm-assistant, and the `/campaign-recall` zvec-grep index. Show the drafts to the GM. File them via `mcp__github__issue_write` only after the GM approves. Once filed, the GM approves an edit adding the `issue:` fields to `mneme/recipes/consumers.yaml`.

---

## Phase 8: Polish, review and release

- [ ] T043 [P] Document `mneme corpus` and the corpus behaviour of `mp render/refresh/status/prune` in `README.md` under the `mneme mp` section.
- [ ] T044 [P] Add a corpus scenario to `tests/integration/test_real_mempalace_e2e.py`, behind `MNEME_REAL_MEMPALACE_VENV`: real `mine --files-from`, `sources --json` and `forget` against a throwaway palace. This verifies the research R1–R4 behaviour against the real binary.
- [ ] T045 (Opus) Full gate: `ruff check hypostasis mneme tests`, `pytest`, and the real-binary lane with `MNEME_REAL_MEMPALACE_VENV` set.
- [ ] T046 (Opus) **Code review phase** (plan § Execution Model): run `/code-review` on the branch diff (`main...007-declared-campaign-corpus`). For each finding, either send it to a Sonnet implementer and re-gate (T045), or record why it is left as is in the PR description. Repeat until the review is clean.
- [ ] T047 (Opus, GM approves) Push `007-declared-campaign-corpus`, then open the PR via `mcp__github__create_pull_request`. The PR body includes the code-review outcome, the T039 migration results, and the follow-up issues from T042.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: none. T002 and T003 run in parallel; T001 is independent.
- **Foundational (Phase 2)**:
  - mempalace T004 → T005 → T006 run in sequence (shared `parser.py`), then T007, then T008 (GM), then T009.
  - The mneme foundations T010–T016 can start as soon as Phase 1 is done. They are tested against the stub.
  - Real-binary use waits on T009.
- **US1 (Phase 3)**: needs Phase 2. This is the MVP.
- **US2 (Phase 4)**: needs US1, because comparison needs corpus mining and the corpus record.
- **US3 (Phase 5)**: needs only Phase 2 (the TOC). It can run in parallel with US1 and US2.
- **US4 (Phase 6)**: T035–T037 need US2 (status rows). T039 (GM) needs US1, US2 and T009 merged and installed.
- **US5 (Phase 7)**: needs only Phase 2 plus `consumers.yaml`. It can run in parallel with US1–US4.
- **Polish (Phase 8)**: needs every story wanted in this release. T046 code review precedes T047.

### Within each story

The implementation tasks come before their integration test, except tasks marked [P],
which touch separate files. The Opus gate closes each phase.

## Parallel Opportunities

- Phase 1: T002 ∥ T003.
- Phase 2: the mempalace chain (T004–T009) runs alongside the mneme chain (T010–T016). Within mneme, T010 ∥ T012. T013 → T014 → T015 are sequential (each builds on the last). T016 is independent.
- After Phase 2, three implementers can run at once: US1 (T018–T022), US3 (T030–T033) and US5 (T040–T041).
- Within US1: T018 ∥ T019. Within US2: T025 ∥ T028, once T024 and T027 land.

### Parallel example: after Phase 2

```text
Implementer A (Sonnet medium): US1  — T018, T019, T020, T021, T022
Implementer B (Sonnet medium): US3  — T030, T031, T032, T033
Implementer C (Sonnet medium): US5  — T040, T041
Opus: gates each story as it lands (T023, T034), then starts US2.
```

## Implementation Strategy

### MVP first

1. Phase 1 and Phase 2, including the merged mempalace PR (T008).
2. Phase 3 (US1). **Stop and validate** with quickstart scenario 1: declared campaigns can no longer fail open.
3. Phase 4 (US2), so the palace is provably exact and prunable.

### Then incremental

4. US3: one TOC for every reader.
5. US4: tooling, then the GM's live migration of obelisk, toee and out-of-the-abyss.
6. US5: compliance in status, plus follow-up issues for the consumer repos.
7. Polish, code review, PR.

## Notes

- **GM checkpoints** (T008, T039, T042, T047 approval) are never delegated. A subagent brief must not include them.
- Every task's implementer brief names the files it may touch. A change outside those files is sent back.
- Commit after each gated phase, on `007-declared-campaign-corpus` only.
