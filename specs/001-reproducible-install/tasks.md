---
description: "Task list for 001-reproducible-install"
---

# Tasks: Reproducible Install & Unified Config

**Input**: Design documents from `specs/001-reproducible-install/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli.md,
contracts/platform-yaml.schema.md, quickstart.md

**Tests**: INCLUDED — plan.md specifies a pytest approach (golden-file render, schema
validation, drift detection, integration loop). Test tasks precede their implementation.

**Organization**: by user story (priority order from spec.md): US1 (P1) → US2 (P2) →
US4 (P2) → US3 (P3). Cross-repo constant removal lives in US1 because SC-002 / US1
acceptance scenario 2 (the grep test) is part of US1's done-ness.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3 / US4 (user-story phases only)

## Path Conventions

Single-project CLI per plan.md: `platform/` package + `platform.yaml` at repo root;
`tests/` at repo root; `specs/001-reproducible-install/validation/` for the SC-005 harness.
Cross-repo edits target `~/src/CampaignGenerator`, `~/src/dgx`, `~/src/mempalace`,
`~/src/mytools/rpg-lib`, `~/src/turbovecdb`(`-service`), `~/campaigns/gm-assistant`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and structure.

- [ ] T001 Create the `platform/` package layout and `pyproject.toml` at repo root (deps: typer, PyYAML, jinja2, httpx, packaging; dev: pytest, ruff) per plan.md structure
- [ ] T002 [P] Configure pytest + ruff/format and the `tests/{unit,integration}/` layout in pyproject.toml / pytest.ini
- [ ] T003 [P] Author a skeleton authoritative `platform.yaml` at repo root from contracts/platform-yaml.schema.md (all six components + services + order; `pin:` values left as TODO placeholders, filled in T015)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The single-authority loader + validation + CLI spine every command needs.

**⚠️ CRITICAL**: No user story can begin until this phase is complete.

- [ ] T004 [P] Implement config entity dataclasses (ConfigEntity, Machine, Service, Component, DerivedConfig) in platform/models.py per data-model.md
- [ ] T005 Implement `platform.yaml` loader with `~`/env expansion in platform/config.py (depends on T004)
- [ ] T006 Implement validation in platform/config.py — schema, referential integrity, acyclicity, exact-pin (reject ranges/editable), single-authority (no lockfile/write-back), path sanity (invariants 1–6 of the schema contract) (depends on T005)
- [ ] T007 Implement the CLI spine in platform/cli.py — typer app, `--config`/`--json`, exit-code convention (0 ok / 1 runtime FAIL / 2 invalid config), subcommands stubbed (depends on T005)
- [ ] T008 [P] Unit tests for config validation (valid; missing field; dangling order ref; cycle; range/editable pin; injected second authority) in tests/unit/test_config.py (depends on T006)

**Checkpoint**: Foundation ready — the authority loads and validates; CLI dispatches.

---

## Phase 3: User Story 1 - Reproducible install from one source of truth (Priority: P1) 🎯 MVP

**Goal**: From one edited `platform.yaml`, one command installs all six components at pins
and renders each component's native config; components read config, not hardcoded constants.

**Independent Test**: On a fresh venv, with only `platform.yaml` edited, run `platform install`
and confirm every component is at its pin with a stamped rendered config, and the grep test
(SC-002) finds the five constants only in config/templates, never in logic.

### Tests for User Story 1

- [ ] T009 [P] [US1] Golden-file render unit tests (`platform.yaml` subtree → expected native config + `source-sha256` stamp) in tests/unit/test_render.py
- [ ] T010 [P] [US1] Integration test for install (throwaway venv → components at pins + config_targets stamped; unresolved pin/partial failure exits non-zero and names the component, FR-006) in tests/integration/test_install.py

### Implementation for User Story 1

- [ ] T011 [P] [US1] Implement the render engine (jinja2; write to `config_target`; stamp `# platform-rendered; source-sha256: <hash>; do-not-edit` header) in platform/render.py (depends on T006)
- [ ] T012 [P] [US1] Create per-component jinja2 templates in platform/templates/ (campaigngenerator.config.yaml.j2, mempalace.yaml.j2, dgxlib.models.yaml.j2, rpg-lib, turbovecdb(-service)) per the config_target paths in the schema contract
- [ ] T013 [US1] Implement the installer (create/validate venv; install each component non-editable at its pin via pip/uv shell-out in `order.install`; fail-loud naming) in platform/install.py (depends on T006)
- [ ] T014 [US1] Wire `platform install` in platform/cli.py to install.py + render.py; verify installed + rendered before exit 0 (depends on T011, T012, T013)
- [ ] T015 [US1] Fill real `pin` (git shas / released versions) + `source` for all six components in platform.yaml (depends on T013)

> Cross-repo constant removal (gated, one repo per task — the actual re-architecture; breaking changes accepted per 2026-06-24 decision). Each reads from its OWN rendered config (Principle VII), not a platform import.

- [ ] T016 [P] [US1] Replace hardcoded constants in ~/src/CampaignGenerator (extract_facts.py `DEFAULT_ENDPOINT`, prep.py, campaignlib/api/backends.py, config/config.yaml 5etools+rpg-lib) with reads from its rendered config (depends on T012, T014)
- [ ] T017 [P] [US1] Replace hardcoded infra assumptions in ~/src/dgx / dgxlib (endpoint/venv) with values from the rendered models.yaml (depends on T012, T014)
- [ ] T018 [P] [US1] Replace hardcoded constants in ~/src/mempalace (backend/device, turbovec endpoint) with reads from its rendered mempalace.yaml (depends on T012, T014)
- [ ] T019 [P] [US1] Replace hardcoded constants in ~/src/mytools/rpg-lib (`localhost:8000`, lib dir) with reads from its rendered config (depends on T012, T014)
- [ ] T020 [P] [US1] Replace hardcoded constants in ~/src/turbovecdb(-service) (port `8077`, venv) with reads from its rendered config (depends on T012, T014)
- [ ] T021 [US1] Update ~/campaigns/gm-assistant skills to reference workspace paths sourced from `platform.yaml` (via CampaignGenerator's rendered config), not hardcoded layout (depends on T014)
- [ ] T022 [US1] Grep-verify SC-002 across all six repos: the five constants appear only in config/templates, zero in logic (depends on T016, T017, T018, T019, T020, T021)

**Checkpoint**: MVP — reproducible install works; constants externalized.

---

## Phase 4: User Story 2 - Honest status by tool (Priority: P2)

**Goal**: One command reports observed installed versions + per-service reachability + render
drift, FAILing on any declared-vs-observed contradiction.

**Independent Test**: With the system installed, `platform status` shows observed-vs-pin and
reachability per service; stop a service or hand-install a wrong version and confirm a FAIL row + exit 1.

### Tests for User Story 2

- [ ] T023 [P] [US2] Unit tests for status (observed-version read; version-drift FAIL; render-drift via stamped-hash mismatch; unreachable-service FAIL; all-PASS→exit 0 / any-FAIL→exit 1) in tests/unit/test_status.py

### Implementation for User Story 2

- [ ] T024 [P] [US2] Implement the health/reachability probe (tcp/http per `service.health`; shared by status and up-gating) in platform/probe.py (depends on T006)
- [ ] T025 [US2] Implement status (observed version via importlib.metadata / `git rev-parse` vs pin; render-drift via stamped hash; reachability via probe; PASS/FAIL rows; exit 1 on any FAIL) in platform/status.py (depends on T011, T024)
- [ ] T026 [US2] Wire `platform status` in platform/cli.py (table + `--json` rows) (depends on T025)

**Checkpoint**: Status is honest (Principle I); no False Green Dashboard.

---

## Phase 5: User Story 4 - Bring the system up/down in dependency order (Priority: P2)

**Goal**: One command starts managed services in declared order (gating on health), one stops
them; the external DGX endpoint is health-checked, not started.

**Independent Test**: From installed-but-stopped, `platform up` starts services in `order.startup`
each reachable before dependents (DGX gated first); a failing start exits 1 and names it; `platform down` stops them.

### Tests for User Story 4

- [ ] T027 [P] [US4] Integration test for lifecycle (up starts managed services in order, gates external DGX reachability first, failed start → exit 1 names service, FR-014; down stops them) in tests/integration/test_lifecycle.py

### Implementation for User Story 4

- [ ] T028 [US4] Implement lifecycle (ordered start of managed services as tracked subprocess + PID/log under ~/.platform/run/ — disposable, non-authoritative; health-gate each via probe before dependents; external deps health-checked not started; down stops by tracked PID, rediscoverable by probe) in platform/lifecycle.py (depends on T024)
- [ ] T029 [US4] Wire `platform up` / `platform down` in platform/cli.py (depends on T028)

**Checkpoint**: System comes up/down in declared order; retires `current-setup.md`.

---

## Phase 6: User Story 3 - Change one value, no stale copies (Priority: P3)

**Goal**: Change one `platform.yaml` value, `platform apply` re-renders affected configs and
restarts affected managed services so no component runs on a stale copy (Principle V).

**Independent Test**: Change `machines.dgx.endpoint`, `platform apply`, confirm every derived
config regenerated and no `config_target` or running process retains the old value; status shows no drift.

> Depends on US4 (the restart mechanism in lifecycle.py) and US1 (render.py).

### Tests for User Story 3

- [ ] T030 [P] [US3] Integration test for apply (one-value change → re-render affected config_targets with fresh stamp + restart affected managed services; zero stale copies; status reports no drift; SC-004) in tests/integration/test_apply.py

### Implementation for User Story 3

- [ ] T031 [US3] Implement `platform apply` (re-render all derived configs; compute affected managed services; restart them via lifecycle; verify no config_target/process retains the prior value) in platform/cli.py (reusing render.py + lifecycle.py) (depends on T011, T028)

**Checkpoint**: Coherence guarantee proven — the V-over-VII mechanism (re-render + restart) works.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Prove reproducibility in isolation; run the quickstart; document.

- [ ] T032 Complete the SC-005 validation harness — make validation/Dockerfile + docker-compose.yml runnable and add validation/run-validation.sh (the install→up→status→change→apply loop, exit non-zero on any FAIL) (depends on T031)
- [ ] T033 [P] Run quickstart.md Scenarios 1–4 on host; fix any gaps (depends on T031)
- [ ] T034 Run quickstart.md Scenario 5 — clean-container acid test (SC-005) via the harness, DGX_MODE=real AND DGX_MODE=stub (assert honest-unreachable) (depends on T032)
- [ ] T035 [P] Docs: add a `platform` README (platform.yaml + CLI usage) and update PLAN.md status (depends on T031)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (P1)**: no dependencies.
- **Foundational (P2)**: depends on Setup — **BLOCKS all user stories**.
- **US1 (P1)**: after Foundational — the MVP.
- **US2 (P2)**: after Foundational — independently testable (reuses render.py from US1 for drift check).
- **US4 (P2)**: after Foundational — independently testable.
- **US3 (P3)**: after US1 (render) **and** US4 (restart) — the one deliberate cross-story dependency (the coherence guarantee needs both).
- **Polish (P7)**: after US3 (the harness runs the full loop).

### Within Each User Story

- Tests written first (and should fail) before implementation.
- Render/installer/probe (libs) before CLI wiring; CLI wiring before cross-repo edits depending on rendered output.
- Cross-repo edits (T016–T021) gated one repo per task; grep-verify (T022) last in US1.

### Parallel Opportunities

- Setup: T002, T003 in parallel.
- Foundational: T004 then T005→T006→T007; T008 after T006.
- US1: T009/T010 (tests) parallel; T011/T012 parallel; cross-repo T016–T020 all parallel (different repos); T022 after them.
- US2: T023 + T024 parallel; then T025→T026.
- US4: T027 parallel with US2 work; T028→T029.
- Polish: T033/T035 parallel; T034 after T032.

---

## Parallel Example: User Story 1 cross-repo edits

```bash
# After T012 (templates) + T014 (install wiring), the six repos edit in parallel:
Task: "Remove hardcoded constants in ~/src/CampaignGenerator (T016)"
Task: "Remove hardcoded constants in ~/src/dgx / dgxlib (T017)"
Task: "Remove hardcoded constants in ~/src/mempalace (T018)"
Task: "Remove hardcoded constants in ~/src/mytools/rpg-lib (T019)"
Task: "Remove hardcoded constants in ~/src/turbovecdb(-service) (T020)"
# Then T022 grep-verifies SC-002 across all of them.
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 → **STOP & VALIDATE**: fresh-venv
   install + SC-002 grep test. This alone removes the bulk of the Infrastructure-Proxy /
   Fragmented-State pain and is demoable.

### Incremental Delivery

US1 (MVP: reproducible install) → US2 (honest status) → US4 (lifecycle up/down) → US3 (apply /
no-stale-copies) → Polish (container acid test SC-005, docs). Each adds value without breaking
the prior. The container acid test in T034 is the definitive SC-005 proof.

### Constitution gates to re-check during implementation

- Every cross-repo edit (T016–T021): component reads its OWN rendered config, never a platform
  import (VII); no new hardcoded constant introduced (II).
- No task introduces a second authoritative store — no lockfile, no written-back config (V).
- `status` (T025) reads observed state, never echoes `platform.yaml` (I).

---

## Notes

- [P] = different files/repos, no incomplete-task dependency.
- Commit after each task or logical group; cross-repo edits are gated and reviewed per repo.
- Two research decisions still flagged ⚠ for ratification (D1 coherence mechanism, D2 DGX
  external) — implementation proceeds under them unless overridden.
- Verify tests fail before implementing.
