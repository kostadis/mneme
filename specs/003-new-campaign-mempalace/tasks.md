---
description: "Task list for Mempalace Bring-Up for a New Campaign"
---

# Tasks: Mempalace Bring-Up for a New Campaign

**Input**: Design documents from `specs/003-new-campaign-mempalace/`

**Prerequisites**: plan.md, spec.md, research.md, research-current-state.md, data-model.md, contracts/

**Tests**: Included — plan.md specifies a unit + integration strategy (extend the 002 stub `mempalace`; golden renders; real-fs backup), consistent with the repo's `tests/unit` + `tests/integration` layout and Principles I/IX.

**Organization**: By user story, priority order. US1 (P1) is the MVP. US2/US3/US5 are P2; US4 is P3. **Greenfield only** — no brownfield/migration logic (GH #24 owns the existing fleet).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no dependency on an incomplete task)
- **[Story]**: US1..US5 (story phases only)

## Path Conventions

Extends the feature-002 `mneme/mempalace/` package and the `mneme mp` CLI group; adds a store-health gate in `mneme/lifecycle.py`. Tests under `tests/unit` + `tests/integration`; fixtures under `tests/fixtures`. Creation-time writes go into the campaign workspace; the global `~/.mempalace/config.json` face is a **merge**; backups land under a configured backups location.

---

## Phase 1: Setup

- [X] T001 Extend the stub `mempalace` in `tests/fixtures/stub_mempalace.py` to honor `--palace <alias|path>`, create a fake `turbovec/<collection>/store.sqlite3` under the resolved palace on `mine`, answer `status --palace`, and record embed/mine calls (so "no re-embed on restore" is assertable)
- [X] T002 [P] Add fixtures in `tests/fixtures/`: a **greenfield** campaign (documents, no `.mneme/`) and a temp backups location + a temp `~/.mempalace` (HOME/XDG override) for store/config.json tests

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The store-pointer authority, the four-face render, the mempalace/store runner+health — everything the bring-up, status, backup, and right-store stories build on.

**⚠️ CRITICAL**: No user-story phase begins until this phase is complete.

- [X] T003 [P] Add 003 dataclasses to `mneme/mempalace/models.py`: `StorePointer` (+ `store` field on `CampaignMempalaceConfig`), `DedicatedStore`, `StoreHealth` (+state), `BindingsBackup`, `BringUpStep`/`BringUpReport`
- [X] T004 Extend `mneme/mempalace/authority.py`: parse/validate the `store:` pointer (alias sanitized, path absolute, exactly one); **refuse a wings-but-no-store-pointer authority** (FR-013/016); serialize `store` in `to_yaml`/`write` (depends on T003)
- [X] T005 [P] Extend `mneme/mempalace/runner.py`: `init`, `mine --palace`, `status --palace`, `search --palace` subprocess wrappers (resolve binary from the venv) (depends on T003)
- [X] T006 Implement the four faces in `mneme/mempalace/render.py` (all stamped): `cli_pointer` (`mempalace.yaml` `palace:`+wings), `cg_search` (`config.yaml` `mempalace:`), `global_alias` (`~/.mempalace/config.json` `palaces:` — **read-modify-merge-write**, never clobber), `mcp` (`.mcp.json` mempalace server, palace injected, never hardcoded) (depends on T004)
- [X] T007 [P] Implement `mneme/mempalace/health.py`: `DedicatedStore` inspection (bindings = `turbovec/*/store.sqlite3`+`knowledge_graph.sqlite3`; rebuildable = `index.tvim`; legacy = `chroma.sqlite3`) + `StoreHealth` (present + turbovec `store_gen`/`tvim` consistency via `runner status`) (depends on T003, T005)
- [X] T008 [P] Foundational unit tests in `tests/unit/test_mp_store_foundation.py`: store-pointer load/validate (incl. **refuse missing pointer**); render golden for all four faces incl. **config.json merge-not-clobber**; health classification of a fixture store

**Checkpoint**: Kernel ready.

---

## Phase 3: User Story 1 - End-to-end bring-up (Priority: P1) 🎯 MVP

**Goal**: One `mneme mp bringup CAMPAIGN` takes a greenfield campaign to configured + faces-rendered + provisioned + first-indexed, with an honest per-step report.

**Independent Test**: Point bring-up at a new campaign with docs and no `.mneme/`; afterward it has the authority+store pointer, all four faces, a built store, and a green report.

- [X] T009 [P] [US1] Unit test in `tests/unit/test_mp_bringup.py`: step order (configure→render→provision→first-mine), idempotent re-run is a no-op, interrupted/failed step ⇒ **not-ready** (never reported ready), no-docs ⇒ "nothing to index yet" (not a failure)
- [X] T010 [P] [US1] Integration test in `tests/integration/test_mp_bringup.py`: end-to-end bringup over the greenfield fixture (stub `mempalace`) — four faces written, store dir created, report green; **Brick Test** (delete store → re-bringup reproduces from docs+authority) (SC-007); **isolation** (SC-005): a sibling campaign's store + faces are byte-unchanged after this bring-up; assert bring-up writes the **active workspace directly** (creation-time path), distinct from the working-copy path (FR-005, U1)
- [X] T011 [US1] Implement `mneme/mempalace/provision.py`: declare the store pointer, render the alias + `palace:` faces, then first `mempalace mine --palace` (sub-scopes-before-root) to **create** the store (depends on T006, T005)
- [X] T012 [US1] Implement `mneme/mempalace/bringup.py`: orchestrate configure (bootstrap authority + store pointer) → render four faces → provision/first-mine → emit `BringUpReport`; idempotent; not-ready on partial. The **backup step delegates to `backup.py`** (US3) — reported as "skipped (US3)" until wired (depends on T011)
- [X] T013 [US1] Implement `mneme mp bringup CAMPAIGN [--dry-run] [--no-backup]` in `mneme/mempalace/cli.py`: dry-run shows steps+faces; real run executes; prints the report; exit 0 iff no step failed (depends on T012)

**Checkpoint**: `mneme mp bringup` is a usable MVP (a new campaign becomes configured, provisioned, indexed, searchable).

---

## Phase 4: User Story 2 - Immediately observable & conformant (Priority: P2)

**Goal**: A just-brought-up campaign appears in `mneme mp status` as built/conformant (never `missing_config`), with store + backup state surfaced (Principle IX).

**Independent Test**: Bring up, run status; the campaign shows built/conformant with store + backup dimensions; the report matches disk.

- [ ] T014 [P] [US2] Unit test in `tests/unit/test_mp_store_status.py`: store dimension (built/stale/missing via `health`), backup-present dimension, a brought-up campaign is conformant (not `missing_config`)
- [ ] T015 [P] [US2] Integration test in `tests/integration/test_mp_store_status.py`: bringup → status shows built/conformant + store/backup state; reported state matches on-disk inspection (SC-002, SC-007 honesty)
- [ ] T016 [US2] Extend `mneme/mempalace/conform.py`: add a **store** dimension (from `health.py`) and a **backup-present** dimension to the per-campaign report (depends on T007)
- [ ] T017 [US2] Extend `mneme mp status` in `mneme/mempalace/cli.py` to surface the store + backup state per campaign (depends on T016)

**Checkpoint**: US1 + US2 — bring up and *see* the new campaign honestly.

---

## Phase 5: User Story 3 - Bindings backup / restore / regenerate (Priority: P2)

**Goal**: Backup preserves the bindings; restore copies them back without re-embedding (turbovecdb rebuilds the index + auto-prunes); re-generation is an explicit verb.

**Independent Test**: Back up, delete the store, restore → search works **without re-embedding**; deleted-source entries pruned; from-scratch re-embed only via `regenerate --confirm`.

- [ ] T018 [P] [US3] Unit test in `tests/unit/test_mp_backup.py`: backup set = `store.sqlite3`+`knowledge_graph.sqlite3`, **excludes** `index.tvim`+`chroma.sqlite3`; restore copies back with **0 embed/mine calls** (stub assertion); `regenerate` requires `--confirm` and re-mines
- [ ] T019 [P] [US3] Integration test in `tests/integration/test_mp_backup.py`: backup → delete store → restore → search works without re-embed; a deleted-source entry is pruned by reconciliation (SC-004); a sibling campaign's store is byte-unchanged after this campaign's backup/restore (SC-005 isolation)
- [ ] T020 [US3] Implement `mneme/mempalace/backup.py`: `backup` (copy bindings set to the backups location, exclude rebuildable/legacy, label derived), `restore` (copy back; never re-embed), `regenerate` (explicit re-`mine`) (depends on T007, T005)
- [ ] T021 [US3] Implement `mneme mp backup|restore|regenerate` in `mneme/mempalace/cli.py`, and **wire the backup step into `bringup.py`** (completing T012's delegated step) (depends on T020, T012)

**Checkpoint**: US1–US3 — bring up, observe, and protect the bindings.

---

## Phase 6: User Story 5 - Right store everywhere: CLI-by-directory + the MCP (Priority: P2)

**Goal**: From inside the campaign directory the CLI resolves to that campaign's store, and the campaign's MCP search targets the same store — zero wrong-store resolutions (SC-008). (The faces are rendered in Foundational T006; this story verifies + guards them.)

**Independent Test**: From each campaign dir the CLI resolves to that store; the `.mcp.json` mempalace face targets the same store; a campaign with the `palace:` face removed is flagged.

- [ ] T022 [P] [US5] Integration test in `tests/integration/test_mp_right_store.py`: run the stub `mempalace` from inside the campaign dir → resolves to the campaign store via the rendered `palace:` face; the `.mcp.json` mcp face names the same store; removing the `palace:` face is flagged (the #21 wrong-store bug)
- [ ] T023 [US5] Extend `mneme/mempalace/conform.py` / `mneme mp status`: assert the `cli_pointer` face and the `.mcp.json` mcp face resolve to the **same** store; flag any wrong-store / missing-pointer (SC-008) (depends on T016, T006)

**Checkpoint**: US1–US3 + US5 — search is pinned to the right store everywhere.

---

## Phase 7: User Story 4 - Idempotent re-run + `mneme up` store-health gate (Priority: P3)

**Goal**: Re-running bring-up is safe; `mneme up` health-gates the store and **fails** if it isn't brought up (never brings it up).

**Independent Test**: Re-run bringup = no-op; `mneme up` on a campaign with a missing/unhealthy store fails with "not brought up", and passes when healthy.

- [ ] T024 [P] [US4] Unit test in `tests/unit/test_mp_up_gate.py`: `lifecycle.up` fails when the store is missing/unhealthy, passes when healthy, and **never** brings the store up
- [ ] T025 [US4] Add the store-health gate to `mneme/lifecycle.py` `up()` (uses `health.py`) — fail (exit 1) with a "mempalace not brought up — run `mneme mp bringup`" message before starting the runtime (depends on T007)
- [ ] T026 [P] [US4] Integration test in `tests/integration/test_mp_idempotent.py`: re-running `mp bringup` on a healthy campaign is a no-op/reported repair; an interrupted bringup is reported not-ready (exercises T012)

**Checkpoint**: All stories independently functional.

---

## Phase 8: Real-environment acid test (Docker — proof environment, not a deployment target)

**Purpose**: prove bring-up works against **real** mempalace(kostadis-dev) + turbovecdb end-to-end, in a clean container with a throwaway `$HOME/.mempalace` — so the test never touches the operator's live campaign stores. Self-contained via the **local ONNX embedder** (no LAN/Spark). Separate lane from the hermetic `pytest` suite (Phases 1–7 use the stub). Mirrors `specs/001-reproducible-install/validation/`.

- [ ] T027 [P] Create `specs/003-new-campaign-mempalace/validation/` (Dockerfile + docker-compose.yml + README) mirroring 001: clean `python:3.11-slim`; `pip install .` (mneme) + install `mempalace` (kostadis-dev) + `turbovecdb`; a small sample campaign baked in; `MEMPALACE_BACKEND=turbovec`, throwaway `HOME=/tmp/...` (throwaway store). **Parameterized by `EMBEDDER`** (both modes):
  - `EMBEDDER=onnx` — install `onnxruntime`, `MEMPALACE_EMBEDDING_PROVIDER=onnx`; **self-contained, no network** (CI/anywhere lane).
  - `EMBEDDER=qwen` — `MEMPALACE_EMBEDDING_PROVIDER=openai-compat`, `MEMPALACE_EMBEDDING_MODEL`/`MEMPALACE_EMBEDDING_ENDPOINT` pointing at the LAN Qwen (injected via `MEMPALACE_EMBEDDING_ENDPOINT`); needs network to the substrate (the real production embedder).
  - docker-compose exposes both as services (`validate-onnx`, `validate-qwen`).
- [ ] T028 Author `specs/003-new-campaign-mempalace/validation/run-validation.sh` (takes `EMBEDDER=onnx|qwen`) — the acid test (exits non-zero on any FAIL, Principle I), run the **same assertions in both modes**:
  - for `qwen`: **first health-gate the embedding endpoint** (reachable? else exit clearly "substrate not up" — never assume, Principle I);
  - real `mneme mp bringup <sample>` → assert the per-campaign turbovec store is created + a real `mneme mp search`/`status` returns over the sample docs;
  - `mneme mp backup` → verify the backup set excludes `index.tvim`/`chroma.sqlite3`;
  - delete the store, `mneme mp restore` → assert search works with **no re-embed** (the embedder is not re-invoked, in either mode) and the campaign is built;
  - `mneme up` **fails** when the store is removed (the gate).
  - Each mode builds its store with its own embedder — no cross-embedder binding mixing (switching embedders is `regenerate`, not `restore`). Runs in the container OR on the host.

## Phase 9: Polish & Cross-Cutting

- [ ] T029 [P] Update `README.md` with `mneme mp bringup|backup|restore|regenerate`, the `mneme up` store-health gate, and the 003 validation container (alongside the 001 one)
- [ ] T030 Run all `quickstart.md` scenarios A–F against the stub fixtures (hermetic lane); fix gaps
- [ ] T031 Run `ruff check hypostasis mneme tests` + full `pytest` (hermetic), then the Docker acid test in **both modes**: `... run --rm validate-onnx` (always) and `... run --rm validate-qwen` (when the LAN Qwen endpoint is up; skips honestly if not); resolve issues
- [ ] T032 [P] Docs note: cross-reference `research-current-state.md` (turbovec backup target) and note the 002 `is_stale` bug (#22) is tracked separately (003 health uses `health.py`, not `is_stale`)

---

## Dependencies & Execution Order

### Phase order
- Setup (P1) → Foundational (P2, **blocks all stories**) → US1 (P3) → US2/US3/US5 (P4–6) → US4 (P7) → Docker acid test (P8) → Polish (P9).

### Cross-story dependencies (delivered earlier by priority)
- **US1 `bringup.py`** has a backup step that **US3 `backup.py`** completes (T021 wires it). US1 ships MVP with backup reported "skipped (US3)".
- **US2 `conform.py`** store/backup dimensions are reused by **US5** (T023) and depend on Foundational `health.py` (T007).
- **US4** up-gate and idempotency test build on Foundational `health.py` (T007) and US1 `bringup.py` (T012).

### Within a story
- Tests `[P]` may be written first; module before its CLI wiring; CLI wiring last.

### Parallel opportunities
- Setup: T002 `[P]`. Foundational: T003/T005/T007/T008 `[P]` (distinct files; T004→T006 and T003→others ordered). Each story's `[P]` test tasks run together. After Foundational, US1/US2/US3/US5 can proceed in parallel; US4 after US1+Foundational.

---

## Parallel Example: Foundational

```bash
Task: "T005 runner.py --palace wrappers in mneme/mempalace/runner.py"
Task: "T007 health.py store inspection + StoreHealth"
Task: "T008 foundational unit tests in tests/unit/test_mp_store_foundation.py"
```

## Implementation Strategy

### MVP (US1 only)
1. Phase 1 Setup → Phase 2 Foundational → Phase 3 US1.
2. **STOP and VALIDATE**: `mneme mp bringup <new-campaign>` end-to-end on a greenfield fixture; campaign is configured, provisioned, indexed, searchable.
3. Backup (US3), richer status (US2), right-store guards (US5), and the up-gate (US4) layer on without breaking US1.

### Notes
- `[P]` = different files, no incomplete-task dependency.
- Greenfield only: no brownfield/migration logic anywhere (GH #24). No hardcoded store paths (render from the authority — kills the CG#112 pattern).
- Restore never re-embeds; only `regenerate` does (FR-012).
- `mempalace` is subprocess-only; backup/restore are filesystem copies of the turbovec `store.sqlite3`.
- **Three test lanes:** (1) hermetic `pytest` (Phases 1–7) with the **stub** `mempalace` — fast, deterministic, the bulk of coverage; (2) Docker acid test **`EMBEDDER=onnx`** — real mempalace+turbovecdb, local embedder, self-contained/CI-able; (3) Docker acid test **`EMBEDDER=qwen`** — same assertions against the **real production embedder** (LAN Qwen), gated on the endpoint being up. All three run against a throwaway `$HOME/.mempalace` (lanes 2–3) so they never touch the operator's live campaign stores — don't run real bring-up directly on the dev box (it would mutate `~/.mempalace/palaces/*`).
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
