---
description: "Task list for Manage Campaign Mempalaces"
---

# Tasks: Manage Campaign Mempalaces

**Input**: Design documents from `specs/002-manage-campaign-mempalaces/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included — plan.md Technical Context specifies a unit + integration strategy (render golden-files, stub `mempalace`, temp-git publish), consistent with the repo's existing `tests/unit` + `tests/integration` layout and Principle I (honest verification).

**Organization**: By user story, priority order. US1 (P1) is the MVP. US2/US3/US5 are P2; US4 is P3.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no dependency on an incomplete task)
- **[Story]**: US1..US5 (story phases only)

## Path Conventions

Single project, extending the existing `mneme/` package. New code under `mneme/mempalace/`, `mneme/mcp/`, `mneme/recipes/`; tests under `tests/unit` and `tests/integration`. Campaign data is written **only** via the private working copy, never the active checkout (FR-018).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project skeleton and dependencies

- [X] T001 Create package skeletons: `mneme/mempalace/__init__.py`, `mneme/mcp/__init__.py`, and `mneme/recipes/` (with `.gitkeep`)
- [X] T002 Add the `mcp` (FastMCP) dependency to `pyproject.toml` (and `[project.scripts]` / extras as needed); confirm `ruff` + `pytest` discovery cover `mneme/mempalace`, `mneme/mcp`
- [X] T003 [P] Create shared test fixtures in `tests/fixtures/`: campaign trees (`full` = 3 wings + `.mempalaceignore` + a per-campaign `MEMPALACE.md` usage guide — the excluded file, distinct from the repo-level `MEMPALACE_HOWTO.md` recipe; `ignore-only`; `bare`×3) and a stub `mempalace` binary (records mine calls, emits a fake drift signal) on `PATH`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared kernel every management command builds on (single authority → stamped renders → observed status). Reuses `hypostasis/render.py` stamping wholesale.

**⚠️ CRITICAL**: No user-story phase can begin until this phase is complete

- [X] T004 [P] Define all dataclasses from data-model.md in `mneme/mempalace/models.py` (Recipe, MechanicalRules, Scaffold, CampaignMempalaceConfig, Wing, Room, Disposition, RenderedWingArtifact, ConformanceRow, `State` enum, ConformanceReport, TargetConfig, MigrationPlan, MigrationStep, WorkingCopy)
- [X] T005 [P] Implement the `mempalace` subprocess helper in `mneme/mempalace/runner.py` (resolve the binary from the configured venv like `lifecycle.py` resolves CG `start`; wrappers for `mine` / `status` / `sync --dry-run` / `split`; parse the source-vs-index drift signal — D2)
- [X] T006 Implement the recipe loader/validator in `mneme/mempalace/recipe.py` per `contracts/recipe.schema.md` (semver, mechanical+scaffold) (depends on T004)
- [X] T007 Author the mneme-owned recipe `mneme/recipes/mempalace.recipe.v1.yaml` per `contracts/recipe.schema.md` (baseline exclusions, sub-scopes-before-root, tunnel rooms, the 3/2/1-wing scaffold), distilled from `MEMPALACE_HOWTO.md`
- [X] T008 [P] Implement the authority loader/validator in `mneme/mempalace/authority.py` per `contracts/campaign-authority.schema.md` (`.mneme/mempalace.yaml`; report all problems at once like `hypostasis/config.py`; forbid second-authority fields) (depends on T004)
- [X] T009 Implement campaign discovery in `mneme/mempalace/discover.py` (enumerate under `data_roots.campaigns`; detect `.mneme/` authority present/absent; list existing wing dirs — those containing a `mempalace.yaml` — for mining) (depends on T004)
- [X] T010 Implement render in `mneme/mempalace/render.py` (authority+recipe → stamped wing `mempalace.yaml` + root `.mempalaceignore`; reuse `hypostasis/render.py` `subtree_sha256`/stamp/`read_stamp`; non-root wing sources added to ignore as the double-mine guard) (depends on T006, T008)
- [X] T011 Register the `mneme mp` Typer sub-group in `mneme/cli.py` (subcommands `status/refresh/render/publish/adopt/migrate/bootstrap/mcp` wired as stubs delegating to their modules; reuse `_load_or_exit`)
- [X] T012 [P] Foundational unit tests in `tests/unit/test_mp_foundation.py`: authority + recipe validation (golden invalid configs), and render golden-file (authority → expected stamped wing yaml + `.mempalaceignore`)

**Checkpoint**: Kernel ready — user stories can proceed.

---

## Phase 3: User Story 1 - Refresh every campaign's mempalace from its own configuration (Priority: P1) 🎯 MVP

**Goal**: One command brings every campaign's index up to date from each campaign's own wing configuration, in the correct order, without hand-running per-wing mining.

**Independent Test**: Point mneme at the campaigns root, run refresh; each configured campaign's index reflects its current docs and its own wings; a no-config campaign is skipped (not failed); an invalid one fails alone.

- [X] T013 [P] [US1] Unit test in `tests/unit/test_mp_refresh.py`: wing mining order (sub-scopes before root), `missing_config` skipped, `invalid_config` isolated, idempotent re-run
- [X] T014 [P] [US1] Integration test in `tests/integration/test_mp_refresh.py`: `discover → refresh --all` over fixtures with the stub `mempalace`; assert per-wing call order and that re-run is a no-op
- [X] T015 [US1] Implement refresh orchestration in `mneme/mempalace/refresh.py` (resolve wings per campaign via `discover`, mine each via `runner` in sub-scopes-before-root order, skip/isolate per FR-006, idempotent per FR-014) (depends on T005, T009)
- [X] T016 [US1] Implement `mneme mp refresh [CAMPAIGN | --all] [--dry-run]` in `mneme/cli.py`: dry-run previews the per-wing plan; real run mines; per-campaign report + exit codes (0 OK / 1 runtime / 2 config) (depends on T015, T011)

**Checkpoint**: US1 fully functional — `mneme mp refresh` is a usable MVP on already-configured campaigns.

---

## Phase 4: User Story 2 - See the true state of every campaign's mempalace (Priority: P2)

**Goal**: Honest cross-campaign status — built / stale / missing-config / divergent — read from the silicon, with every divergence paired with its recorded disposition or flagged undispositioned.

**Independent Test**: Run status over mixed-state fixtures; each campaign is classified from observed state; a hand-edited derived file is caught as stale-render; shared backing store is not conflated.

- [X] T017 [P] [US2] Unit test in `tests/unit/test_mp_conform.py`: every `State` value; disposition classification (deliberate/pending/undispositioned); deliberate-recorded is NOT a FAIL; undispositioned IS; shared-store non-conflation (FR-013)
- [X] T018 [P] [US2] Integration test in `tests/integration/test_mp_status.py`: honest status over `full`/`ignore-only`/`bare` fixtures; hand-edit a derived wing yaml → stale-render FAIL; reported state matches on-disk inspection (SC-007)
- [X] T019 [US2] Implement conformance in `mneme/mempalace/conform.py`: `index` dim from `runner` drift (D2), `render` dim from stamp coherence (`render.py`/`hypostasis.render`), `recipe` dim from authority-vs-recipe diff paired with `Disposition`; emit `ConformanceRow`/`State`; undispositioned is derived, never written (FR-005/008/027) (depends on T010, T006, T008, T005)
- [X] T020 [US2] Implement `mneme mp status [CAMPAIGN]` in `mneme/cli.py`: per-campaign rows; exit 0 iff no genuine FAIL (`divergent_deliberate` not a FAIL; `divergent_undispositioned`/`invalid_config`/stale-render are; `stale` under `--strict`); `missing_config` reported + skipped (depends on T019, T011)
- [X] T021 [US2] Implement `mneme mp render CAMPAIGN --check` (read-only coherence report) in `mneme/cli.py` (depends on T010, T011)

**Checkpoint**: US1 + US2 both work independently — you can see and refresh every campaign.

---

## Phase 5: User Story 3 - Propagate a newly discovered best practice (Priority: P2)

**Goal**: Publish a recipe upgrade to every campaign as a version-controlled proposal in the private working copy (never the active checkout); each campaign adopts on its own side.

**Independent Test**: Publish in preview lists per-campaign changes; apply pushes a proposal branch while the active checkout stays byte-unchanged; a conflict with a deliberate choice is surfaced, not applied.

- [X] T022 [P] [US3] Implement `mneme/mempalace/target.py`: resolve the current recipe against a campaign's authority, preserving non-conflicting choices, producing a `TargetConfig` + diff; surface conflicts with deliberate dispositions (FR-009) (depends on T006, T008)
- [X] T023 [US3] Implement `mneme/mempalace/workcopy.py`: private clone of the campaigns repo under XDG state; commit + push a proposal branch `mneme/recipe-<ver>`; guarantee the active checkout is never written (FR-018); optional `gh` PR (depends on T004)
- [X] T024 [P] [US3] Unit test in `tests/unit/test_mp_target.py`: recipe-resolution preserves non-conflicting choices; conflict with a deliberate disposition is surfaced (FR-009/SC-004)
- [X] T025 [P] [US3] Integration test in `tests/integration/test_mp_publish.py`: publish against a temp git remote; assert proposal branch pushed AND active checkout `git status` byte-unchanged (SC-009)
- [X] T026 [US3] Implement `mneme mp publish [--recipe VER] [--dry-run] [--open-pr]` in `mneme/cli.py`: render upgrades into the working copy (T010), preview per campaign, commit + push branch; canonical config unchanged until adoption (depends on T022, T023, T010, T011)
- [X] T027 [US3] Implement `mneme mp adopt CAMPAIGN` in `mneme/cli.py`: campaign-side mechanical (non-migration) upgrade applied in the working copy; bump `recipe_version` in the authority; per-campaign opt-in (FR-021) (depends on T022, T023, T010, T011)

**Checkpoint**: US1–US3 independent — publish-once / adopt-per-campaign works for mechanical upgrades.

---

## Phase 6: User Story 5 - Adopt a new scheme and migrate, assistant-guided (Priority: P2)

**Goal**: Serve the per-campaign target config + inventory over an advisory MCP server; execute a human-approved, free-form migration plan in the working copy, preserving content verbatim and verifying the actual result.

**Independent Test**: Retrieve target config via the MCP tool; an approved plan splits a bible verbatim; post-migration verification confirms the actual index conforms; an interrupted migration is never reported healthy.

**Note**: Builds on US2 `conform.py` (post-migration verification, FR-026) and US3 `target.py` + `workcopy.py`.

- [X] T028 [US5] Implement `mneme/mempalace/migrate.py`: execute an approved `MigrationPlan` in the working copy; closed content-preserving op set (`move/split/rename/reindex/write_authority`); reject any content-rewriting step (FR-025); re-run conformance after apply (FR-026); resumable/idempotent so an interrupted migration is never healthy (depends on T019, T023, T010)
- [X] T029 [US5] Implement the advisory MCP server in `mneme/mcp/server.py` (FastMCP): read-only tools `get_target_config` (FR-022), `get_status`, `get_campaign_inventory`; no mutation tool (depends on T022, T019, T009)
- [X] T030 [US5] Implement `mneme mp migrate CAMPAIGN --plan PLAN.json [--dry-run]` (require `approved_by_human: true`) and `mneme mp mcp` in `mneme/cli.py` (depends on T028, T029, T011)
- [X] T031 [P] [US5] Unit test in `tests/unit/test_mp_migrate.py`: verbatim guard rejects a content-rewrite step; plan without `approved_by_human` is refused; post-migration non-conformance distinguishes incomplete from deliberate
- [X] T032 [P] [US5] Integration test in `tests/integration/test_mp_migrate.py`: `get_target_config`/`get_campaign_inventory` via MCP; approved plan splits a bible with byte-identical content (SC-010); verification catches a deliberately-incomplete plan

- [X] T042 [US5] Author the mneme-owned **management instructions** in `mneme/recipes/instructions/manage-mempalace.md` (the `MEMPALACE_HOWTO.md` method as the served, versioned-with-recipe payload, FR-029)
- [X] T043 [US5] Extend `mneme/mcp/server.py` to serve instructions on demand (FR-028): an MCP prompt/resource for `manage_mempalace` (mneme-owned) and a per-campaign `campaign_usage_guide` resource read from the campaign's `MEMPALACE.md` (read-only, loaded on demand) (depends on T029)
- [X] T044 [P] [US5] Integration test in `tests/integration/test_mp_instructions.py`: load `manage_mempalace` and a campaign's `campaign_usage_guide` via MCP with zero pasted docs (SC-013); usage guide is read from the campaign, not mneme; server-down ⇒ GM workflow unaffected

**Checkpoint**: US1–US3 + US5 — the full publish → adopt → migrate loop works under the safety invariants, with the method served on demand.

---

## Phase 7: User Story 4 - Bootstrap a standard mempalace into a campaign that has none (Priority: P3)

**Goal**: Write a starter authority (from the recipe scaffold) into a campaign with no config, in the working copy, for the owner to customize; also the scatter→single-authority consolidation (FR-017).

**Independent Test**: Bootstrap a bare campaign; starter `.mneme/mempalace.yaml` appears in the working copy; a subsequent refresh builds its index.

- [X] T033 [P] [US4] Unit test in `tests/unit/test_mp_bootstrap.py`: starter authority generated from the scaffold; consolidation folds existing scattered wing yamls into one authority (FR-017)
- [X] T034 [US4] Implement bootstrap/consolidation in `mneme/mempalace/bootstrap.py`: generate a starter `.mneme/mempalace.yaml` from the recipe scaffold; consolidate any existing scattered wing yamls into the authority (depends on T006, T008, T010)
- [X] T035 [US4] Implement `mneme mp bootstrap CAMPAIGN` in `mneme/cli.py`: write into the working copy under preview-then-apply (FR-010/018) (depends on T034, T023, T011)
- [X] T036 [P] [US4] Integration test in `tests/integration/test_mp_bootstrap.py`: bootstrap a `bare` fixture → authority present → refresh builds the index

**Checkpoint**: All five user stories independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T037 [P] Update `README.md` with the `mneme mp` command table and the per-campaign authority/derived-render model
- [X] T038 Run all `quickstart.md` scenarios A–G against fixtures; fix gaps
- [X] T039 Run `ruff check hypostasis mneme tests` + full `pytest`; resolve lint/format/test issues across the new packages
- [X] T040 [P] Add a docs note cross-referencing `MEMPALACE_HOWTO.md` ↔ the mneme-owned recipe (prose rationale vs enforceable counterpart, FR-015)
- [X] T041 [P] Integration test (**Brick Test** — FR-011 / SC-005 / Principle IV) in `tests/integration/test_mp_bricktest.py`: build the fixture campaigns, run `mneme mp status` and capture the report; then destroy ALL mneme-local state (the XDG state dir + the private working copy) and reinstall the package; re-run `mneme mp status` and assert the report is byte-identical with zero re-entered per-campaign config — proving the manager owns nothing irreplaceable and reconstructs from the campaigns alone

---

## Phase 9: Proposal-aware status (follow-on — GH #14)

**Purpose**: Surface mneme-created proposal branches as a git-level to-do list on `status`
(the observability gap caught by use; the broader constitution gap is recorded as GH #11).

- [X] T045 Implement `mneme/mempalace/proposals.py` (read-only git: list `mneme/*` origin branches; classify merged/pending vs HEAD; campaigns touched; degrade to `[]` off-repo)
- [X] T046 Add a TODO section to `mneme mp status` in `mneme/cli.py` (`--no-proposals` / `--no-fetch`; informational, never changes exit code — FR-021)
- [X] T047 [P] Tests: `tests/unit/test_mp_proposals.py` (non-git degrade + TODO formatting) and `tests/integration/test_mp_proposals.py` (real git: pending → merged)

---

## Phase 10: Confirm-gated MCP adopt (follow-on — FR-030, decision 2026-06-26)

**Purpose**: Let a chat/agentic harness drive per-campaign adoption. Deliberate, recorded
relaxation of FR-018: writes the active checkout, but only single-campaign, confirm-gated,
mneme-managed files only, uncommitted.

- [X] T048 Implement `publish.adopt_in_place` (write upgraded authority + renders into the active checkout; mneme-managed files only; never campaign content; uncommitted) + amend spec FR-018/add FR-030 + update `contracts/mcp-tools.md`
- [X] T049 Add the `adopt_campaign(campaign, confirm)` MCP tool (preview → confirm) in `mneme/mcp/server.py`, and a `--here/--confirm` mode on `mneme mp adopt`
- [X] T050 [P] Test `tests/integration/test_mp_adopt_mcp.py`: preview writes nothing; confirm writes only mneme files (campaign content byte-unchanged); no-authority → error, not a write

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (P1)**: no dependencies
- **Foundational (P2)**: depends on Setup — BLOCKS all stories
- **US1 (P3)**: after Foundational — the MVP, no dependency on other stories
- **US2 (P4)**: after Foundational — independent of US1
- **US3 (P5)**: after Foundational — independent (uses Foundational `render`)
- **US5 (P6)**: after Foundational; **builds on US2 `conform.py` and US3 `target.py`/`workcopy.py`** (delivered earlier by priority)
- **US4 (P7)**: after Foundational; uses US3 `workcopy.py`
- **Polish (P8)**: after all desired stories

### Within Each User Story

- Tests `[P]` can be written first and in parallel; module before its CLI wiring; CLI wiring last.

### Parallel Opportunities

- Setup: T003 `[P]`.
- Foundational: T004, T005, T008, T012 `[P]` (distinct files); T006→T010 and T008→T010 are ordered; T007/T009/T011 independent.
- Each story's `[P]` test tasks run together; within a story the module task precedes its CLI task.
- With capacity, after Foundational: US1, US2, US3 can proceed in parallel; US5 starts once US2+US3 land; US4 once US3 lands.

---

## Parallel Example: Foundational

```bash
# After T004 lands, these are independent:
Task: "T005 mempalace subprocess helper in mneme/mempalace/runner.py"
Task: "T008 authority loader/validator in mneme/mempalace/authority.py"
Task: "T012 foundational unit tests in tests/unit/test_mp_foundation.py"
```

## Parallel Example: User Story 2

```bash
Task: "T017 unit test conform states in tests/unit/test_mp_conform.py"
Task: "T018 integration test honest status in tests/integration/test_mp_status.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → Phase 2 Foundational → Phase 3 US1.
2. **STOP and VALIDATE**: `mneme mp refresh --all` over the real campaigns; confirm each builds from its own wings.
3. Usable immediately (replaces hand-running per-wing mining).

### Incremental Delivery

1. Foundation → US1 (refresh, MVP) → demo.
2. US2 (status) → you can now *see* divergence and staleness.
3. US3 (publish/adopt) → roll best practice out; adopt per campaign.
4. US5 (migrate) → assistant-guided data migrations under the safety invariants.
5. US4 (bootstrap) → onboard the bare campaigns.

### Notes

- `[P]` = different files, no incomplete-task dependency.
- Every write to campaign data goes through the working copy (T023) — never the active checkout (FR-018 / SC-009).
- The deterministic paths (refresh/conform/render/publish) carry no LLM; the LLM appears only in the human-approved migration plan (US5), fenced by verbatim (FR-025) + write-isolation (FR-018) + post-migration verification (FR-026).
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
