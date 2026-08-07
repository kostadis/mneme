---
description: "Task list for feature 006 — Portable vs Host-Local Campaign State"
---

# Tasks: Portable vs Host-Local Campaign State

**Input**: Design documents from `specs/006-portable-campaign-state/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all complete)

**Tests**: INCLUDED — the spec's success criteria (SC-001…SC-008) are explicit and verifiable,
and the repo is test-driven (`tests/unit`, `tests/integration`, 125+ tests green today).

**Organization**: By user story (US1–US4 from spec.md) in priority order. Phase 1 carries a
**hard external prerequisite** (GH #35); Phase 2 is shared plumbing that blocks both P1 stories.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete-task dependency)
- All paths are repo-relative to `/home/kroussos/src/mneme` on branch `006-portable-campaign-state`

## Sequencing constraints that are NOT negotiable

1. **T002–T004 (GH #35) come first.** Three of this feature's requirements put a full tree scan
   on code paths that previously had none (FR-002, FR-016a, FR-018). Until discovery stops
   following symlinks out of the campaigns root, those paths hang on any host carrying one.
2. **US4 comes after US1.** FR-018 removes the `--dir` ownership bypass, which is the *only*
   workaround available today. FR-019 forbids a window where a legitimately-owned campaign is
   unmanageable by both routes — so the identity remedy must land first.
3. **The live-fleet migration (T053) and the release are one deployment.** Under FR-014 each
   host finds a *different* campaign fatal; a half-deployed fleet has one broken campaign per
   machine.

---

## Phase 1: Setup & the #35 prerequisite

**Purpose**: A green baseline, and the discovery fix every later tree scan depends on.

- [X] T001 Run baseline `pytest tests/unit tests/integration` and `ruff check .` to confirm a green starting point before any change.
- [X] T002 [P] Skip symlinked children when enumerating campaigns (`child.is_symlink()` guard) in `discover()` in `mneme/mempalace/discover.py:75-78`.
- [X] T003 [P] Replace the unbounded `rglob("mempalace.yaml")` with a symlink-bounded walk (`os.walk(..., followlinks=False)`) in `_existing_wing_dirs` in `mneme/mempalace/discover.py:45-50`.
- [X] T004 [P] Unit test: a campaigns root containing a symlinked directory is not treated as a campaign, and wing discovery does not escape the campaign dir, in `tests/unit/test_discover.py` (depends T002, T003).

**Checkpoint**: `mneme mp status` returns in under a second with a symlink under the campaigns root (quickstart Scenario 0). GH #35 is closeable.

---

## Phase 2: Foundational — host store root + ownership evidence (Blocking Prerequisites)

**Purpose**: Two pure additions that block both P1 stories. Neither changes existing behavior.

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

- [X] T005 [P] Add `mempalace_root(entity) -> Path` using the existing `single_root(entity, "mempalace")` helper, defaulting to `~/.mempalace`, in `hypostasis/config.py` (beside `single_root` at `:68-78`).
- [X] T006 [P] Add read-only `owner_ids(campaign_dirs) -> dict[str, list[str]]` (owner id → campaign names), built on the existing `read_owner`, in `mneme/mempalace/ownership.py`.
- [X] T007 [P] Extend `make_entity` to accept an optional `mempalace` data root in `tests/fixtures/__init__.py`.
- [X] T008 [P] Unit tests for `mempalace_root`: declared value wins, absent defaults to `~/.mempalace`, multi-valued declaration raises `ConfigError`, in `tests/unit/test_config.py`.
- [X] T009 [P] Unit tests for `owner_ids`: groups campaigns by owner id, ignores un-integrated campaigns, returns empty for an empty tree, in `tests/unit/test_ownership.py`.

**Checkpoint**: helpers exist and are tested; nothing else references them yet; full suite still green.

---

## Phase 3: User Story 1 — A second machine manages the campaigns it owns (Priority: P1) 🎯 MVP

**Goal**: A host with no fleet identity adopts the fleet's existing one instead of minting its own, so a shared checkout is manageable from both machines.

**Independent Test**: On a host with no `mneme:` block, pointed at a tree whose campaigns name one identity, mneme refuses to mint and names the adopt remedy; after `mneme identity adopt <id>`, every name-based command resolves those campaigns as owned.

### Tests for User Story 1

- [X] T010 [P] [US1] Unit tests for the adopt-or-mint decision table — 0 owner ids → mint, 1 → refuse naming the id and campaigns, >1 → refuse listing all — in `tests/unit/test_identity.py`.
- [X] T011 [P] [US1] Unit test: `adopt_mneme_identity` appends a `mneme:` block when absent and replaces only that block when present, preserving all other content and comments, in `tests/unit/test_identity.py`.
- [X] T012 [P] [US1] Unit test: `adopt_mneme_identity` rejects a malformed id before writing, and refuses when the current identity owns campaigns unless `force=True`, in `tests/unit/test_identity.py`.
- [X] T013 [P] [US1] Integration test: with campaigns owned by id A and no local identity, `mneme up <campaign>` refuses, writes nothing to `hypostasis.yaml`, and names both remedies; after adopt, status shows `OWNED`, in `tests/integration/test_membership.py`.

### Implementation for User Story 1

- [X] T014 [US1] Add `adopt_mneme_identity(config_path, id, *, label=None, force=False)` beside `ensure_mneme_identity` in `hypostasis/config.py:323-339`, reusing its append-don't-rewrite discipline and replacing only the `mneme:` block when one exists.
- [X] T015 [US1] Add a `resolve_identity(entity, config_path)` helper implementing the FR-002/003/004 decision table (mint on zero evidence, refuse on one or many) using `owner_ids` from T006, in `mneme/cli.py`.
- [X] T016 [US1] Rework `_ensure_identity` to call `resolve_identity` instead of minting unconditionally, in `mneme/cli.py:65-71` (depends T015).
- [X] T017 [US1] Add the `mneme identity` Typer sub-app with `show`, `adopt <id> [--label] [--force]`, and `mint [--label]` per `contracts/identity-lifecycle.md`, in `mneme/cli.py` (depends T014, T015).
- [X] T018 [US1] Make `identity show` report the established id, its label, its source file, and the campaigns it owns — or, when unestablished, the evidence plus both remedies — exiting 0 in both cases, in `mneme/cli.py` (depends T017).
- [X] T019 [US1] Update the `UNVERIFIABLE` membership note from "run `mneme integrate` to mint" to the adopt-or-mint choice in `_membership_row` in `mneme/mempalace/conform.py:141-145`.

**Checkpoint**: quickstart Scenario 3 passes. The live host can adopt `64cf8b36-…` and see both campaigns `OWNED`. SC-004 verifiable.

---

## Phase 4: User Story 2 — The tracked authority is identical on every machine (Priority: P1)

**Goal**: `store.path` leaves the tracked authority; the palace location derives from the host root plus the alias, so the shared repo stops accumulating host-attributable diffs.

**Independent Test**: Write an authority on one host, read it on a host with a different palace root, and confirm the two resolve *different* locations from *identical* file bytes, with neither host rewriting the file.

### Tests for User Story 2

- [X] T020 [P] [US2] Unit test: `to_yaml` emits `store: {alias: ...}` and never a `path` key, in `tests/unit/test_mp_store_foundation.py`.
- [X] T021 [P] [US2] Unit test: the same authority bytes loaded with two different `mempalace_root` values resolve two different `store.path` values, and re-serializing is a fixed point under both, in `tests/unit/test_mp_store_foundation.py` (replaces the `is_absolute()` assertion at `:43`).
- [X] T022 [P] [US2] Unit test: an authority with no `store` block still loads as `store=None` and `require_store` still refuses it (002-era compatibility), in `tests/unit/test_mp_store_foundation.py`.
- [X] T023 [P] [US2] Integration test: `bringup` then `render` under two entities differing only in `data_roots.mempalace` leaves the authority byte-identical and each host's faces naming its own root, in `tests/integration/test_mp_right_store.py`.

### Implementation for User Story 2

- [X] T024 [US2] Derive `store.path` as `mempalace_root / "palaces" / alias` instead of reading `sraw["path"]`, in `_parse` in `mneme/mempalace/authority.py:94-104`.
- [X] T025 [US2] Add `*, mempalace_root: Path | None = None` to `load()` (defaulting to `~/.mempalace`) and thread it into `_parse` and `validate`, in `mneme/mempalace/authority.py:238-255` (depends T024).
- [X] T026 [US2] Emit only `{"alias": ...}` for the store block in `to_yaml`, in `mneme/mempalace/authority.py:205-206`.
- [X] T027 [US2] Document `StorePointer.path` as derived and in-memory-only, never serialized, in `mneme/mempalace/models.py:83-89`.
- [X] T028 [P] [US2] Resolve `default_config_json` and `_default_store` from `mempalace_root(entity)` instead of the hardcoded `~/.mempalace`, in `mneme/mempalace/bringup.py:27-33`.
- [X] T029 [P] [US2] Resolve `_default_store` from `mempalace_root(entity)` in `mneme/mempalace/bootstrap.py:35-37`.
- [X] T030 [P] [US2] Resolve the status `config_json` from `mempalace_root(entity)` in `_store_backup_rows` in `mneme/mempalace/conform.py:117`.
- [X] T031 [US2] Thread `mempalace_root(entity)` into `_authority.load(...)` at `mneme/mempalace/bringup.py:39,117` and `mneme/mempalace/backup.py:40,114` (depends T025).
- [X] T032 [P] [US2] Thread `mempalace_root(entity)` into `_authority.load(...)` at `mneme/mempalace/publish.py:52,62,150` (depends T025).
- [X] T033 [P] [US2] Thread `mempalace_root(entity)` into `_authority.load(...)` at `mneme/mempalace/conform.py:164` and `mneme/mempalace/cli.py:162` (depends T025).
- [X] T034 [P] [US2] Thread `mempalace_root(entity)` into `_authority.load(...)` at `mneme/mcp/server.py:32,77,111` (depends T025).
- [X] T035 [US2] Verify the three store-naming faces still render the resolved location with no edit to `mneme/mempalace/render.py:184,207,238` (FR-015), and add an assertion covering it to the T023 integration test.

**Checkpoint**: quickstart Scenarios 1 and 2 pass. SC-002, SC-003, SC-005 verifiable. A legacy `path:` is silently ignored at this point — US3 adds the comparison.

---

## Phase 5: User Story 3 — Legacy authorities are surfaced, never silently re-pointed (Priority: P2)

**Goal**: A legacy `store.path` that agrees with the derived location is reported as owed cleanup; one that disagrees is a hard failure naming both, so no populated store is ever silently abandoned.

**Independent Test**: Load an authority whose stored path equals the derived location and see it load with a status to-do; load one whose stored path differs and see every operation fail before any side effect.

**Depends on**: US2 (there is no derived location to compare against until T024–T026 land).

### Tests for User Story 3

- [X] T036 [P] [US3] Unit test: a legacy `store.path` equal to the derived location loads successfully and is flagged as legacy, in `tests/unit/test_mp_store_foundation.py`.
- [X] T037 [P] [US3] Unit test: a legacy `store.path` different from the derived location raises `AuthorityError` naming both locations, in `tests/unit/test_mp_store_foundation.py`.
- [X] T038 [P] [US3] Unit test: a legacy path that differs only via symlink or trailing separator resolves equal and does NOT raise, in `tests/unit/test_mp_store_foundation.py`.
- [X] T039 [P] [US3] Integration test: with one campaign conflicted, `mp status` reports it invalid-config naming both locations AND reports every other campaign in full; no store directory is created or modified, in `tests/integration/test_mp_store_status.py`.

### Implementation for User Story 3

- [X] T040 [US3] Replace the `store.path` absolute-path rule with the legacy comparison — resolve both sides, equal is accepted, different is a problem naming both — in `validate` in `mneme/mempalace/authority.py:172-176`.
- [X] T041 [US3] Expose whether the loaded authority carried a legacy path (so status can report it without re-reading the file), in `mneme/mempalace/authority.py` (depends T040).
- [X] T042 [US3] Add the "legacy store.path — remove it (host-local, no longer tracked)" to-do row to the per-campaign status rows in `mneme/mempalace/conform.py:87-125` (depends T041).
- [X] T043 [US3] Confirm the existing `AuthorityError` catch at `mneme/mempalace/conform.py:165-168` yields one invalid-config row and does not abort the fleet run (FR-014a); add the missing-dimension note to that row.

**Checkpoint**: quickstart Scenario 4 passes both cases. SC-007 verifiable.

---

## Phase 6: User Story 4 — Refusals apply to every route and say what to do (Priority: P3)

**Goal**: Ownership is enforced however a campaign was named, duplicate aliases are refused, and every refusal names both identities and the remedy.

**Independent Test**: A foreign campaign is refused whether named by name or by `--dir`; two campaigns sharing an alias fail any operation touching either; the messages name the owner, this mneme, and the next step.

**Depends on**: US1 — FR-019 forbids removing the `--dir` bypass before the adopt remedy exists.

### Tests for User Story 4

- [X] T044 [P] [US4] Integration test: a foreign campaign named via `--dir` is refused with the same message as the name route, in `tests/integration/test_membership.py`.
- [X] T045 [P] [US4] Integration test: two campaigns declaring the same `store.alias` fail any operation touching either, naming both campaigns and the alias; neither store is read or written, in `tests/integration/test_mp_right_store.py`.
- [X] T046 [P] [US4] Unit test: the foreign-owner message contains the campaign's owner id, this mneme's id (or its absence), and the `mneme identity adopt` remedy, in `tests/unit/test_ownership.py`.

### Implementation for User Story 4

- [X] T047 [US4] Move the foreign-owner exclusion out of `find()` so name resolution no longer performs ownership classification, in `mneme/mempalace/discover.py:83-106`.
- [X] T048 [US4] Enforce the ownership gate in the command layer on whatever `resolve()` returns, so `--dir` and name routes are treated identically, in `mneme/mempalace/cli.py` and `mneme/cli.py:55-62,120-128` (depends T047).
- [X] T049 [US4] Add the fleet-level alias-uniqueness check over the discovered set, applied to both routes, in `mneme/mempalace/discover.py` (depends T047).
- [X] T050 [P] [US4] Rewrite the foreign-owner refusal to name both ids and the adopt remedy, in `mneme/mempalace/discover.py:92-97`, `mneme/mempalace/ownership.py:87-96`, and `mneme/cli.py:122-128`.

**Checkpoint**: quickstart Scenarios 5 and 6 pass. SC-008 verifiable.

---

## Phase 7: Polish, documentation & the live-fleet migration

- [X] T051 [P] Document `data_roots.mempalace` (optional, defaults to `~/.mempalace`) in `hypostasis.example.yaml:23-31`.
- [X] T052 [P] Correct the commented `mneme:` block in `hypostasis.example.yaml:19-21` — a second host **adopts** the fleet's existing id rather than minting its own.
- [X] T053 Migrate the live fleet: `mneme identity adopt 64cf8b36-e823-4b8e-8353-d08fe707f9be`, then delete the `path:` line under `store:` in `~/campaigns/toee/.mneme/mempalace.yaml` and `~/campaigns/obelisk/.mneme/mempalace.yaml`, and commit both in the `~/campaigns` repo (depends US1–US3; ships with the release, not before).
- [X] T054 Run quickstart Scenario 7 end-to-end: `mneme mp status`, `mneme mp render obelisk --check` **without** `--dir` (the GH #51 repro), and confirm `git -C ~/campaigns diff` is empty after a render (depends T053).
- [X] T055 [P] Run the full suite and linter: `pytest tests/unit tests/integration` and `ruff check .`.
- [ ] T056 [P] Close GH #35 (fixed by T002–T004) and GH #51 (fixed by this feature); note on GH #30 that its tracking decision is now unblocked, and that `~/.mempalace/config.json` and `.mcp.json` must stay untracked per `contracts/mempalace-yaml.schema.md`.

---

## Dependencies

```
Phase 1 (T001–T004, GH #35)
        │
        ▼
Phase 2 (T005–T009, shared helpers)
        │
        ├─────────────────────┐
        ▼                     ▼
Phase 3 US1 (P1)        Phase 4 US2 (P1)      ← independent of each other
   identity                store.path
        │                     │
        │                     ▼
        │              Phase 5 US3 (P2)       ← needs the derived location
        │                     │
        ▼                     │
Phase 6 US4 (P3) ◄────────────┘               ← needs US1's remedy (FR-019)
        │
        ▼
Phase 7 (T051–T056, docs + live migration)
```

**Story independence**: US1 and US2 are genuinely independent — one is the identity half, the
other the store half, sharing only Phase 2's helpers. Either alone is a shippable improvement.
US3 depends on US2; US4 depends on US1.

## Parallel execution examples

**Phase 1** — T002, T003 touch the same file but different functions; do T002 then T003, and
T004 after both.

**Phase 2** — T005, T006, T007 are three different files: fully parallel. T008, T009 follow.

**Phase 3 + Phase 4 together** — the largest parallel win. US1 touches `hypostasis/config.py`
and `mneme/cli.py`; US2 touches `mneme/mempalace/*`. The only shared file is
`mneme/mempalace/conform.py` (T019 vs T030), which touches different functions.

**Phase 4 threading** — T032, T033, T034 are three disjoint file sets, all depending only on
T025: run them in parallel. T028, T029, T030 likewise.

## Implementation strategy

**MVP = Phase 1 + Phase 2 + Phase 3 (US1).** That alone makes the second machine able to manage
its own campaigns — the reported failure — and is independently valuable even if the store half
slips. Note it does *not* stop the `store.path` ping-pong; `obelisk` still fails on this host
with `Permission denied` until US2 lands.

**Recommended increment order**: US1 → US2 → US3 → US4 → migrate. US2 immediately after US1
because both are P1 and together they close GH #51 completely; US3 must follow US2; US4 last
because it is the one behavior change that removes an existing workaround.

**Release atomicity**: T053 (the campaigns-repo edit) and the mneme release ship together. Under
FR-014 each host finds a different campaign fatal, so a partial rollout leaves every machine
with one unloadable campaign.
