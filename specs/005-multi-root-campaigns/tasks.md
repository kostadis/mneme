---
description: "Task list for feature 005 — Multi-Root Campaign Discovery & Membership"
---

# Tasks: Multi-Root Campaign Discovery & Membership

**Input**: Design documents from `specs/005-multi-root-campaigns/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all complete)

**Tests**: INCLUDED — the spec's success criteria (SC-001…SC-009) are explicit and verifiable,
and the repo is test-driven (`tests/unit`, `tests/integration`).

**Organization**: By user story (US1–US6 from spec.md) in priority order. Phase 2 is a shared
config-layer change that blocks the stories.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete-task dependency)
- All paths are repo-relative to the worktree root `~/src/mneme-005-multi-root/`

---

## Phase 1: Setup

- [x] T001 Run baseline `pytest tests/unit tests/integration` in the worktree to confirm a green starting point before changes.

---

## Phase 2: Foundational — `data_roots` becomes one-or-more (Blocking Prerequisites)

**Purpose**: The config-layer type change every story builds on. Keeps backward compatibility (US2) free.

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

- [x] T002 [P] Change `data_roots` field to `dict[str, tuple[Path, ...]]` in `hypostasis/models.py`.
- [x] T003 Normalize scalar-or-list per key in `_parse`, add per-element absolute-path check and `campaigns` overlap/nesting rejection in `validate`, and add a `single_root(entity, key) -> Path` helper in `hypostasis/config.py` (depends T002).
- [x] T004 [P] Emit each `data_roots` value as a list of strings in `hypostasis/render.py`.
- [x] T005 [P] Resolve the `backups` root via `single_root(entity, "backups")` in `mneme/mempalace/backup.py`.
- [x] T006 [P] Update `make_entity` / fixtures to build tuple-valued `data_roots["campaigns"]` in `tests/fixtures/__init__.py` (and adjust direct `data_roots=` constructions in `tests/unit/test_*`).
- [x] T007 [P] Unit tests for the config shape: scalar→1-tuple, list→N-tuple, per-element absolute rejection, overlapping-trees rejection, `single_root` >1 error, in `tests/unit/test_config.py`.

**Checkpoint**: config layer compiles and parses both shapes; `test_config` green.

---

## Phase 3: User Story 1 — Discover campaigns across several trees (Priority: P1) 🎯 MVP

**Goal**: Fleet-wide operations see campaigns from all declared trees as one fleet.

**Independent Test**: Declare two trees; `mneme mp status` lists every campaign from both, deterministically, read-only.

### Tests for User Story 1

- [x] T008 [P] [US1] Unit test `discover()` enumerates campaigns across two trees with correct `path`/`tree` and deterministic `(name, tree)` ordering, in `tests/unit/test_discover.py`.
- [x] T009 [P] [US1] Integration test: `status` lists campaigns from two trees and writes nothing (assert tree mtimes unchanged, no network), in `tests/integration/test_multiroot_status.py`.

### Implementation for User Story 1

- [x] T010 [US1] Add `tree: Path` field to `CampaignRef` in `mneme/mempalace/discover.py`.
- [x] T011 [US1] Rename `campaigns_root` → `campaigns_roots(entity) -> tuple[Path, ...]`, validating each tree exists, in `mneme/mempalace/discover.py` (depends T010, T003).
- [x] T012 [US1] Rewrite `discover()` to iterate every tree × immediate subdirs, set `tree`, and sort by `(name, tree)`, in `mneme/mempalace/discover.py` (depends T011).
- [x] T013 [US1] Rewrite `find(entity, name)` for multi-tree resolution — single match returns it, zero matches raises a not-found error listing the trees searched, in `mneme/mempalace/discover.py` (depends T012). *(Ambiguity handled in US3.)*
- [x] T014 [US1] Resolve the campaign workspace via `find()` across trees in `_campaign_dir` (keep the `--dir` override) in `mneme/lifecycle.py` (depends T013).
- [x] T015 [US1] Update per-tree git callers to `campaigns_roots`: per-tree origin in `_clone_workcopy` (`mneme/mempalace/publish.py`) and per-tree proposal listing (`mneme/mempalace/cli.py`), satisfying FR-009 (depends T011).
- [x] T016 [US1] Update `status` to enumerate and display campaigns across all trees in `mneme/mempalace/conform.py` and `mneme/mempalace/cli.py` (depends T012).

**Checkpoint**: Multi-tree discovery + status works end-to-end; full suite green. **MVP deliverable.**

---

## Phase 4: User Story 2 — Existing single-location setups keep working (Priority: P2)

**Goal**: A scalar `data_roots.campaigns` behaves exactly as before.

**Independent Test**: Point at one location with the scalar shape; discovery/status output matches pre-feature behavior.

### Tests for User Story 2

- [x] T017 [P] [US2] Unit test: scalar `data_roots.campaigns` yields the same `CampaignRef` set as a 1-element list (parity), in `tests/unit/test_discover.py`.
- [x] T018 [P] [US2] Integration test: a single-location config produces unchanged `status` output, in `tests/integration/test_backcompat.py`.

*(Implementation is the foundational normalization, T003; US2 is the verification story.)*

**Checkpoint**: Backward compatibility proven (SC-002).

---

## Phase 5: User Story 3 — Never silently resolve an ambiguous campaign (Priority: P2)

**Goal**: A name present under >1 tree fails loudly, naming the trees; no side effect.

**Independent Test**: Same-named campaign in two trees; a name-based command errors naming both trees.

### Tests for User Story 3

- [x] T019 [P] [US3] Unit tests: `find()` raises an ambiguity error naming every tree on >1 match, and the not-found error lists searched trees, in `tests/unit/test_discover.py`.

### Implementation for User Story 3

- [x] T020 [US3] Extend `find()` to raise an explicit ambiguity `DiscoveryError` (campaign + every tree) when >1 non-foreign match, before any side effect, in `mneme/mempalace/discover.py` (depends T013).

**Checkpoint**: Ambiguity is impossible to resolve silently (SC-003).

---

## Phase 6: User Story 4 — Claim (`mneme integrate`) & self-declared ownership (Priority: P2)

**Goal**: Explicit claim drops `.mneme/owner.yaml`; `up` integrates-then-provisions; foreign-owned refused & surfaced; boot/status read-only.

**Independent Test**: `integrate` creates only `owner.yaml`; a hand-edited foreign `owner.yaml` is refused and flagged; `up` auto-integrates an unowned campaign.

### Tests for User Story 4

- [x] T021 [P] [US4] Unit tests for `classify()` (UNINTEGRATED/OWNED/FOREIGN) and `ensure_mneme_identity()` (mints once, idempotent, textual append preserves existing content), in `tests/unit/test_ownership.py` and `tests/unit/test_identity.py`.
- [x] T022 [P] [US4] Integration tests: `integrate` writes only `owner.yaml`; `up` auto-integrates then provisions; foreign-owned causes `integrate`/`up` to refuse and `status` to flag it (no re-stamp), in `tests/integration/test_membership.py`.

### Implementation for User Story 4

- [x] T023 [P] [US4] Add `MnemeIdentity(id, label)` dataclass + `ConfigEntity.mneme_identity` field in `hypostasis/models.py`.
- [x] T024 [US4] Parse the `mneme:` block (validate `id` non-empty if present) and add `ensure_mneme_identity(config_path)` (uuid4 mint via targeted text append, reports identity) in `hypostasis/config.py` (depends T023).
- [x] T025 [P] [US4] Echo the mneme identity in `hypostasis/render.py`.
- [x] T026 [P] [US4] New module `mneme/mempalace/ownership.py`: `OwnerState`, `Owner`, `read_owner`, `classify`, `write_owner` (writes only `.mneme/owner.yaml`, no host field).
- [x] T027 [US4] Add `owner_state` to `CampaignRef` and populate it in `discover()` via `classify()` (UNVERIFIABLE when no identity) in `mneme/mempalace/discover.py` (depends T012, T026).
- [x] T028 [US4] Exclude FOREIGN from `find()`'s match set and surface it separately in `mneme/mempalace/discover.py` (depends T020, T027).
- [x] T029 [US4] New `mneme integrate <campaign>` command (resolve, classify, refuse FOREIGN, idempotent OWNED, mint+`write_owner` UNINTEGRATED) in `mneme/cli.py` (depends T024, T026).
- [x] T030 [US4] Extend `mneme up` to refuse FOREIGN and integrate-first when UNINTEGRATED in `mneme/lifecycle.py` and `mneme/mempalace/bringup.py` (depends T029).
- [x] T031 [US4] Report membership state (OWNED/FOREIGN/UNINTEGRATED/UNVERIFIABLE) in `status` in `mneme/mempalace/conform.py` and `mneme/mempalace/cli.py` (depends T027).

**Checkpoint**: Ownership lifecycle + foreign refusal + read-only boot all work (SC-006, SC-007).

---

## Phase 7: User Story 5 — Owner is a logical identity, not a machine (Priority: P3)

**Goal**: `owner.yaml` is host-free; ownership = id match across runtimes.

**Independent Test**: Inspect `owner.yaml` (no host field); same id → OWNED, different id → FOREIGN.

### Tests for User Story 5

- [x] T032 [P] [US5] Contract/unit test: `write_owner` output contains no host/machine/path key, and `classify()` is identity-only (same id OWNED on a different simulated runtime, different id FOREIGN), in `tests/unit/test_ownership.py`.
- [x] T033 [P] [US5] Integration Brick-Test: a fresh config reusing the same `mneme.id` re-adopts claimed campaigns from `owner.yaml` alone; a different id classifies them FOREIGN, in `tests/integration/test_membership.py`.

*(Implementation guaranteed by the US4 `owner.yaml` schema; US5 enforces/verifies the invariant — SC-008, SC-009.)*

**Checkpoint**: Host-independent ownership model proven; cross-machine bring-up not precluded.

---

## Phase 8: User Story 6 — Resolve the toee split-brain (Priority: P3, acid test)

**Goal**: Validate the feature against the real motivating scenario.

**Independent Test**: Declare monorepo + toee trees; toee managed from its own tree; duplicate surfaced; resolved by editing only the trees list.

- [x] T034 [US6] Execute quickstart.md scenarios 5–7 (foreign-owned refusal, ambiguity, Brick Test) against a two-tree fixture and record results in the PR description / a scratch log.
- [x] T035 [US6] Dry-run the toee topology (monorepo tree + a toee tree) confirming SC-004 — toee resolvable by editing only `data_roots.campaigns`, no other path edits. *(The actual `~/toee` ↔ `~/campaigns/toee` data migration is post-feature operational work, tracked separately.)*

**Checkpoint**: Acid test passes; ready to return to the real toee migration.

---

## Phase 9: Polish & Cross-Cutting

- [x] T036 [P] Update `specs/001-reproducible-install/contracts/hypostasis-yaml.schema.md` to document the `data_roots` list form and the `mneme:` identity block (or reference the 005 delta contract).
- [x] T037 [P] Update `hypostasis.example.yaml` with a two-tree `data_roots.campaigns` and an example `mneme:` block.
- [x] T038 Run full `pytest` and the `quickstart.md` validation end-to-end in the worktree.
- [x] T039 [P] Update any operator docs / `CLAUDE.md` notes referencing single-root assumptions.

---

## Dependencies & Execution Order

### Phase order
- **Setup (P1)** → **Foundational (P2, blocks all)** → **US1 (P3)** → US2/US3/US4 (P2 stories) → US5/US6 (P3) → **Polish (P9)**.
- The suite goes fully green at the **US1 checkpoint** (MVP); foundational alone leaves `discover.py` mid-refactor.

### Story dependencies
- **US1** depends only on Foundational.
- **US2** depends on Foundational (verification of T003); independent of US1 logic.
- **US3** depends on US1 (`find()` exists).
- **US4** depends on US1 (`discover()`/`find()`/`CampaignRef`); T028 also depends on US3's T020 (shared `find()`).
- **US5** depends on US4 (owner.yaml + classify).
- **US6** depends on US1–US5 (it validates the whole).

### Shared-file coordination (avoid parallel conflicts)
- `mneme/mempalace/discover.py` — touched by US1 (T010–T013), US3 (T020), US4 (T027–T028). Sequence these, do not parallelize across stories.
- `mneme/mempalace/conform.py` + `cli.py` (status) — touched by US1 (T016) and US4 (T031). Sequence.
- `hypostasis/config.py` — T003 (foundational) then T024 (US4). Sequence.

### Parallel opportunities
- Foundational: T002, T004, T005, T006, T007 in parallel (distinct files) after/with T003 where noted.
- Tests marked [P] within a story run together (distinct test files).
- US4 model/module tasks T023, T025, T026 in parallel (distinct files) before the wiring tasks.

---

## Implementation Strategy

### MVP first
1. Phase 1 + Phase 2 (foundational config change).
2. Phase 3 (US1) → **STOP, validate**: multi-tree discovery + status, suite green. This alone delivers the headline capability.

### Incremental delivery
US2 (prove back-compat) → US3 (ambiguity safety) → US4 (ownership + `integrate`) → US5 (host-independent invariant) → US6 (acid test) → Polish. Each story is an independently testable increment.

---

## Notes
- `[P]` = different files, no incomplete dependency.
- Commit after each task or logical group; keep the suite green at the US1 checkpoint onward.
- The only brand-new source file is `mneme/mempalace/ownership.py` (T026); all else edits existing files mapped in plan.md.
- Out of scope (do NOT build here): driving git (clone/fetch/sparse), cross-machine bring-up *execution*, and the live toee data migration.
