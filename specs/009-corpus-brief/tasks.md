---

description: "Task list for feature 009 — corpus brief"
---

# Tasks: Corpus Brief

**Input**: Design documents from `specs/009-corpus-brief/`

**Prerequisites**: plan.md, spec.md (US1–US5), research.md (R1–R12), data-model.md, contracts/,
quickstart.md

**Tests**: Included. The plan's Structure lists the test files, and quickstart scenarios 1–7
and SC-003/004/005/007 each need an automated check.

**Organization**: Grouped by user story. Priority order: US1, US2, US3 (P1), then US5 (P2,
the migration), then US4 (P3, consumer inventory).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US5 from spec.md
- **Who does it** (GM execution policy, mneme#92): every task goes to a **Sonnet
  implementer subagent** unless marked **(Opus)** (the orchestrator does it) or **(GM)** (a
  human checkpoint; no agent performs it). Opus reviews each phase's diff and runs the suite
  before starting the next phase.
- **Paths**: relative to the worktree `~/src/mneme-009` (created in T001).
- **Leftovers**: anything not finished, and every confirmed review finding not fixed in the
  single review pass (T029), becomes a sub-issue of kostadis/mneme#92 (T030).

## Rules every implementer brief carries

- Read the task's contract file(s) in `specs/009-corpus-brief/contracts/` first. They are
  binding. Where the WIP spike (commit 739851f) disagrees with a contract, the contract wins.
- Work only in `~/src/mneme-009`. `~/src/mneme` is the live editable install every mneme
  command runs from; never edit it. Before trusting a green run, confirm
  `python -c "import mneme; print(mneme.__file__)"` from the worktree's pytest resolves under
  `~/src/mneme-009` (`pyproject.toml` sets `pythonpath = ["."]`).
- One resolution per request (research R3): never call `config.load()` a second time after
  a resolution in the same answer.
- The brief answer never queries the palace and never contains file contents or a per-file
  listing outside `brief` (FR-007, FR-007a, R5).
- Refusal codes are exactly `not-declared`, `invalid`, `no-brief`, `brief-unavailable`
  (answer) and additionally `brief-exists`, `brief-undeclared` (migration). Discovery errors
  propagate unchanged.
- Match the surrounding 007 code's style. Comments are sparse and cite the FR or research item.
- Never run pytest inside `git rebase --exec`.

---

## Phase 1: Setup

**Purpose**: Workspace, and take the spike out of the live install.

- [ ] T001 (Opus) Commit the planning artifacts (`specs/009-corpus-brief/`, `.specify/feature.json`) on branch `corpus-brief` in `~/src/mneme`. Then `git -C ~/src/mneme switch main` (so the live editable install stops running the spike) and `git -C ~/src/mneme worktree add ~/src/mneme-009 corpus-brief`. Verify `mneme corpus --help` no longer lists `brief`, and that `~/src/mneme-009` has the spike commit 739851f in its history.
- [ ] T002 (Opus) In `~/src/mneme-009`, revert the spike's consumer-inventory change: restore the `skill.campaign-prep` row in `mneme/recipes/consumers.yaml` and the pinned counts in `tests/unit/test_corpus_consumers.py` to `main`'s versions (`git checkout main -- <both paths>`), and drop the spike's `test_campaign_prep_skill_reads_grounding_through_the_toc`. That row becomes `mode: brief` in the mytools#87 work, not here (plan § Post-design re-check). Run `python -m pytest -q tests` → all green.

---

## Phase 2: Foundational (blocking)

**Purpose**: The declaration parses, validates against the corpus, and resolves once. Every story needs this.

- [ ] T003 Rework `brief:` parsing in `mneme/corpus/config.py` (spike code exists) to the contract `contracts/corpus-yaml-brief.md` and `data-model.md` § Brief: `brief` in `_TOP_KEYS`; `CorpusConfig.brief: tuple[str, ...] = ()`; `_brief()` reports `malformed` (not a list of strings; an entry listed twice), `path-escape` (via `_norm`), `empty-declaration` (`brief: []`), all collected with the other findings before raising.
- [ ] T004 Rework the membership check in `mneme/corpus/resolve.py` (spike code exists): a `brief-undeclared` finding (path = the entry) for every entry that is not a resolved file path of any kind and not in any kind's `not_materialized` or `missing`. Folders, gitignored files and files outside every kind all land here (research R1/R2).
- [ ] T005 Refactor `mneme/corpus/api.py` so one resolution serves every reader (research R3): introduce an internal `_resolve_now(campaign_dir, recipe) -> (CorpusConfig, ResolvedCorpus, toc_doc)` that reads `corpus.yaml` once; `fresh()` and `consult()` use it with unchanged behaviour and return shapes. Delete the spike's `brief()` body (it is rewritten in T010). Existing 007 tests must pass unchanged.
- [ ] T006 [P] Unit tests in `tests/unit/test_corpus_brief_config.py` (new): each structural finding from T003 and `brief-undeclared` from T004, using a corpus built like `tests/fixtures/corpus_campaign.py`'s `CORPUS_YAML` in a real git repo. Cover: `brief: [docs/npcs]` (folder), an undeclared file, a gitignored file inside a declared dir, a duplicate, `[]`, `../x.md`, a non-list; a valid `brief: [docs/planning.md]` passes; a brief entry that is declared but not materialized is NOT a finding. Assert all findings of one bad file are reported together.

**Checkpoint**: `python -m pytest -q tests` green; `mneme corpus check` (from the worktree) fails on a bad brief and passes on a good one.

---

## Phase 3: User Story 1 — a briefing consumer loads exactly the load-now set (P1) 🎯 MVP

**Goal**: `mneme corpus brief` and MCP `corpus_brief` return the brief plus the per-kind map.

**Independent Test**: In the fixture campaign with `brief: [docs/planning.md]`, the answer names exactly that file with its size and has one `kinds` entry per declared kind, with no per-file listing.

- [ ] T007 [P] [US1] Unit tests in `tests/unit/test_corpus_brief_answer.py` (new), against `api.brief()`: declared order kept for a two-entry brief; a file shared by two kinds lists both kinds in declaration order and one trust; `bytes` equals `os.stat` of the declared path (symlink → target size); `brief_bytes` is the sum; `kinds{}` has exactly `standard, trust, files, bytes, searchable, searchable_files` per kind; `searchable_files` counts only `minable` files with non-null `mined_as` (add a `.pdf` to a declared dir to prove it is excluded); `corpus_sha256` equals the sha256 of the file bytes; no key anywhere holds a file's contents. Mock or stub nothing in the palace and assert the runner is never constructed (FR-007a).
- [ ] T008 [P] [US1] Integration tests in `tests/integration/test_corpus_brief_readers.py` (new), modelled on `tests/integration/test_corpus_toc_readers.py`: the CLI `corpus brief --json` output equals MCP `server.corpus_brief(entity, "corp")` (SC-004); adding `docs/npcs/b.md` raises `kinds.npcs.files` by one on the next call with no render (SC-005); the serialized answer is < 2048 bytes for the fixture (SC-007); the human form prints the brief files then one line per kind.
- [ ] T009 [US1] Implement `api.brief(campaign_dir, recipe) -> dict` in `mneme/corpus/api.py` on top of `_resolve_now` (T005), exactly per `contracts/brief-json.md` and `data-model.md` § Answer states: return `{"brief": doc}` or `{"error", "detail", "findings"}`; `not-declared`/`invalid` reuse `consult`'s messages; `no-brief` when `cfg.brief == ()`; `brief-unavailable` naming every brief entry that is not a resolved file on this checkout. Sizes measured at call time.
- [ ] T010 [US1] Rework `mneme corpus brief` in `mneme/corpus/cli.py` (spike code exists) per `contracts/cli.md`: `--json` prints the answer; the human form prints `brief (N file(s), B bytes):`, one line per brief file with kinds and bytes, then `kinds:` and one line per kind (`trust`, `files`, `bytes`, `searchable_files`). Refusals go through `_refuse` (exit `EXIT_RUNTIME`).
- [ ] T011 [US1] Rework `corpus_brief` in `mneme/mcp/server.py` (spike code exists): a module-level `corpus_brief(entity, campaign)` returning the answer dict or `{campaign, error, detail}`, registered as tool `corpus_brief` with a docstring that tells the assistant to read only `brief[].path`, search for the rest, and refuse on `error`.

**Checkpoint**: T007/T008 green; Opus runs `mneme corpus brief corp --json` in the fixture by hand and reviews the shape against `contracts/brief-json.md`.

---

## Phase 4: User Story 2 — the GM declares and checks the brief (P1)

**Goal**: `corpus check` reports the brief, and the skeleton shows how to declare one.

**Independent Test**: `corpus check` on a valid corpus prints `brief: 1 file(s), 43304 bytes` (or `brief: not declared`); on a bad brief it fails naming the entry.

- [ ] T012 [P] [US2] Tests in `tests/integration/test_corpus_brief_readers.py`: `corpus check` prints `brief: N file(s), B bytes` / `brief: not declared` as its penultimate line, before `corpus is valid`; a `brief-undeclared` corpus exits non-zero with the finding on stderr; `corpus toc` refuses on the same corpus (FR-002: the whole corpus is invalid).
- [ ] T013 [US2] Rework the `check` command in `mneme/corpus/cli.py`: take the brief count and bytes from the same resolution (`_resolve_now`), not a second `load()` (the spike calls `_cconfig.load` again; remove that).
- [ ] T014 [P] [US2] Add a commented `brief:` example to `_skeleton()` in `mneme/corpus/cli.py` (`# brief:          # optional: files a briefing consumer loads up front` / `#   - docs/planning.md`), and a test in `tests/unit/test_corpus_brief_config.py` that the skeleton still parses with `brief` absent (`CorpusConfig.brief == ()`).

**Checkpoint**: Stories 1 and 2 both work.

---

## Phase 5: User Story 3 — consumers refuse instead of guessing (P1)

**Goal**: Every refusal path returns no file list and a distinct, actionable code.

**Independent Test**: Each of the five cases in spec US3 produces its code and no `brief` key.

- [ ] T015 [P] [US3] Tests in `tests/integration/test_corpus_brief_readers.py`, one per case, each asserting the code, a non-empty `detail`, and the absence of any `brief`/`kinds` key: no `corpus.yaml` → `not-declared`; an invalid corpus → `invalid` with the same findings `corpus check` prints; no `brief:` → `no-brief` (and the answer is NOT the map alone, FR-011); a brief file declared but deleted from disk → `brief-unavailable` naming it; a second checkout of the fixture campaign passed via `--dir` → the store-alias `DiscoveryError` from CLI and MCP (Story 3, scenario 5). CLI cases assert exit `EXIT_RUNTIME` and `error:` on stderr (FR-012).
- [ ] T016 [US3] Fix whatever T015 exposes in `mneme/corpus/api.py` / `cli.py` / `mneme/mcp/server.py`. If T015 passes first time, record that in the task note and change nothing.

**Checkpoint**: All P1 stories complete — the MVP.

---

## Phase 6: User Story 5 — the GM migrates existing corpora (P2)

**Goal**: `mneme corpus migrate-brief` previews, then appends, a `brief:` block.

**Independent Test**: Preview writes nothing; apply appends exactly the previewed block and every other byte is unchanged; a second run refuses `brief-exists`.

- [ ] T017 [P] [US5] Unit tests in `tests/unit/test_brief_migrate.py` (new), on a fixture corpus whose `corpus.yaml` has comments, blank lines and no trailing newline: preview returns the block and per-file kinds/bytes and leaves the file's bytes identical; apply leaves the original bytes as an exact prefix of the new file (a single inserted newline if the original lacked one) followed by `brief:\n  - docs/planning.md\n`; the result passes `config.parse` and a fresh resolution; `--file` order is kept; refusals, each writing nothing: `not-declared`, `invalid`, `brief-exists` (also for `brief: null` and for a commented-out-then-real key), `brief-undeclared` (`--file docs/nope.md`), `brief-unavailable` (declared but absent); a simulated failure before the replace leaves the original file intact (atomicity).
- [ ] T018 [US5] Implement `mneme/corpus/brief_migrate.py` (new) per research R11 and `data-model.md` § Brief migration: `plan(campaign_dir, recipe, files) -> Plan | Refusal` (decides by parsing, never writes) and `apply(plan) -> Path` (append, validate the new bytes with `config.parse` + a resolution against them, then `mneme.atomic` replace). Never YAML-dumps the file. Default `files = ("docs/planning.md",)`.
- [ ] T019 [US5] Add `mneme corpus migrate-brief` to `mneme/corpus/cli.py` per `contracts/cli.md`: `CAMPAIGN` or `--all` (exactly one), repeatable `--file`, `--apply`, plus `--dir`/`--config`. `--all` iterates owned campaigns from `discover(entity)`; each campaign prints `== <name>` then its preview / `applied` / `refused: <code>: <detail>`; a discovery error for one campaign is that campaign's refusal. Exit 0 iff no campaign refused (FR-020).
- [ ] T020 [P] [US5] Integration tests in `tests/integration/test_corpus_brief_readers.py`: CLI preview then `--apply` on the fixture, then `corpus brief` answers; `--all` over two fixture campaigns where one already has a brief → the other is applied, the run exits non-zero, and the first campaign's file is untouched.
- [ ] T021 [P] [US5] Regression test for research R12 in `tests/integration/test_corpus_brief_readers.py` (or beside the existing adopt tests): a corpus with `brief:` and a campaign kind that the adopted recipe makes standard keeps its `brief:` block byte-for-byte after `corpus_guard.migrate_shadowed` / `mp adopt --here`, and still validates. If it does not, fix `mneme/mempalace/corpus_guard.py` so it does.

**Checkpoint**: Migration works on the fixture; live preview happens in T037.

---

## Phase 7: User Story 4 — the consumer inventory knows about briefing consumers (P3)

**Goal**: `mode: brief` is a compliant consumer mode, and the obligations say when to use the brief.

**Independent Test**: A `consumers.yaml` row with `mode: brief` is reported compliant.

- [ ] T022 [P] [US4] Add `"brief"` to `MODES` and map it to `compliant` in `mneme/corpus/consumers.py`; update the header comment of `mneme/recipes/consumers.yaml` (`mode: palace | toc | brief (compliant) · partial · independent`). No row changes (T002).
- [ ] T023 [P] [US4] Tests in `tests/unit/test_corpus_consumers.py`: a synthetic row with `mode: brief` parses and `compliance()` is `compliant`; an unknown mode still errors; the shipped file's pinned counts are unchanged from `main`.
- [ ] T024 [P] [US4] Add consumer obligations 4 and 5 to `mneme/recipes/instructions/manage-mempalace.md` § Consumer obligations, verbatim from `contracts/consumer-obligations.md`, and a `no-brief` / `brief-unavailable` / `brief-undeclared` row to its § Remedies table pointing at `mneme corpus migrate-brief` / `mneme corpus check`. Run the existing instructions tests (`tests/integration/test_mp_instructions.py`) and update any pinned text they check.

---

## Phase 8: Polish & cross-cutting

- [ ] T025 [P] Add a "Delta: 009" note at the top of `specs/007-declared-campaign-corpus/contracts/corpus-yaml.md` and `specs/007-declared-campaign-corpus/contracts/cli.md` pointing to `specs/009-corpus-brief/contracts/`, so a reader of 007 finds `brief:`.
- [ ] T026 (Opus) Run the full suite in the worktree (`python -m pytest -q tests`), confirm `mneme.__file__` resolves to the worktree, and record the counts.
- [ ] T027 (Opus) Live, read-only validation from the worktree against the GM's four campaigns (quickstart 1, 2, 3, 7): `corpus brief` refuses `no-brief`; `migrate-brief <c>` previews for obelisk, toee, out-of-the-abyss and Phandalin and `git status` shows each `corpus.yaml` unchanged; `--file docs/nope.md` refuses; stormgiants refuses `not-declared`; `~/src/campaigns/obelisk` refuses the store-alias clash. Use `python -m mneme.cli` from `~/src/mneme-009` (not the live `mneme`). No `--apply`.
- [ ] T028 (Opus) Commit the feature in logical commits on `corpus-brief` (Foundational; US1; US2+US3; US5; US4+docs), each message ending with the Co-Authored-By line.
- [ ] T029 (Opus) Run ONE `/code-review` pass over `main...corpus-brief`. Fix confirmed findings that are small and in scope, in one follow-up commit, and run the suite again. Do not run a second review.
- [ ] T030 (Opus) File every confirmed review finding not fixed in T029, every unchecked task, and every gap deferred during implementation as a sub-issue of kostadis/mneme#92 (`issue_write` with `parent_issue_number: 92`), each with the failing scenario and the file:line.
- [ ] T031 (Opus) Push `corpus-brief` and open a PR against `main` that closes #92 and lists its sub-issues. Do not merge without the GM's go-ahead.
- [ ] T032 (GM) Review the PR and merge it. Then run `mneme corpus migrate-brief --all` (preview), check each proposal, run `--apply`, and commit each campaign's `corpus.yaml` in the campaigns repo (quickstart 6).

---

## Dependencies & Execution Order

### Phase dependencies

- Setup (T001–T002) → Foundational (T003–T006) → user stories → Polish.
- US1 (T007–T011) needs T005. US2 (T012–T014) needs T003/T004 and touches `cli.py` after T010.
  US3 (T015–T016) needs T009–T011. US5 (T017–T021) needs T003–T005 only and can start alongside
  US1. US4 (T022–T024) needs nothing beyond Setup.
- T026–T032 run in order after every story.

### Story dependencies

- US1 is the MVP. US2 and US3 extend it, but share no files with US5 or US4 except `cli.py`.
- `cli.py` is touched by T010, T013, T014 and T019: those run sequentially, in that order.

### Within each story

Tests (marked [P]) are written first and fail; the implementation then makes them pass.

## Parallel Example

```text
After T005:
  Agent A: T007 + T008 (US1 tests)        Agent B: T017 (US5 unit tests)
  Agent C: T022 + T023 + T024 (US4)
Then: T009 → T010 → T011 (US1), while Agent B does T018; then T013/T014, T019 in cli.py order.
```

## Implementation Strategy

1. **MVP**: Setup + Foundational + US1 + US3 gives a working, refusing `corpus brief`, enough to
   convert `campaign-prep` once a brief is declared by hand.
2. Add US2 (check/skeleton) and US5 (migration) so the GM can declare briefs safely.
3. Add US4 (inventory mode, obligations).
4. One review pass, sub-issues for the rest, PR, GM merge and live migration.
