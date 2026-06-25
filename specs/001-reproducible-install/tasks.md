---
description: "Task list for 001-reproducible-install"
---

# Tasks: Reproducible Install & Unified Config

**Input**: Design documents from `specs/001-reproducible-install/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli.md,
contracts/mneme-yaml.schema.md, quickstart.md

**Tests**: INCLUDED — plan.md specifies a pytest approach (golden-file render, schema
validation, drift detection, integration loop). Test tasks precede their implementation.

**Organization**: by user story (priority order from spec.md): US1 (P1) → US2 (P2) →
US4 (P2) → US3 (P3). Cross-repo constant removal lives in US1 because SC-002 / US1
acceptance scenario 2 (the grep test) is part of US1's done-ness.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3 / US4 (user-story phases only)

## Path Conventions

Single-project CLI per plan.md: `mneme/` package + `mneme.yaml` at repo root;
`tests/` at repo root; `specs/001-reproducible-install/validation/` for the SC-005 harness.
Cross-repo edits target `~/src/CampaignGenerator`, `~/src/dgx`, `~/src/mempalace`,
`~/src/mytools/rpg-lib`, `~/src/turbovecdb`(`-service`), `~/campaigns/gm-assistant`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and structure.

- [X] T001 Create the `mneme/` package layout and `pyproject.toml` at repo root (deps: typer, PyYAML, jinja2, httpx, packaging; dev: pytest, ruff) per plan.md structure
- [X] T002 [P] Configure pytest + ruff/format and the `tests/{unit,integration}/` layout in pyproject.toml / pytest.ini
- [X] T003 [P] Author a skeleton authoritative `mneme.yaml` at repo root from contracts/mneme-yaml.schema.md (all six components + services + order; `pin:` values left as TODO placeholders, filled in T015)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The single-authority loader + validation + CLI spine every command needs.

**⚠️ CRITICAL**: No user story can begin until this phase is complete.

- [X] T004 [P] Implement config entity dataclasses (ConfigEntity, Machine, Service, Component, DerivedConfig) in mneme/models.py per data-model.md
- [X] T005 Implement `mneme.yaml` loader with `~`/env expansion in mneme/config.py (depends on T004)
- [X] T006 Implement validation in mneme/config.py — schema, referential integrity, acyclicity, exact-pin (reject ranges/editable), single-authority (no lockfile/write-back), path sanity (invariants 1–6 of the schema contract) (depends on T005)
- [X] T007 Implement the CLI spine in mneme/cli.py — typer app, `--config`/`--json`, exit-code convention (0 ok / 1 runtime FAIL / 2 invalid config), subcommands stubbed (depends on T005)
- [X] T008 [P] Unit tests for config validation (valid; missing field; dangling order ref; cycle; range/editable pin; injected second authority) in tests/unit/test_config.py (depends on T006)

**Checkpoint**: Foundation ready — the authority loads and validates; CLI dispatches.

---

## Phase 3: User Story 1 - Reproducible install from one source of truth (Priority: P1) 🎯 MVP

**Goal**: From one edited `mneme.yaml`, one command installs all six components at pins
and renders each component's native config; components read config, not hardcoded constants.

**Independent Test**: On a fresh venv, with only `mneme.yaml` edited, run `mneme install`
and confirm every component is at its pin with a stamped rendered config, and the grep test
(SC-002) finds the five constants only in config/templates, never in logic.

### Tests for User Story 1

- [X] T009 [P] [US1] Golden-file render unit tests (`mneme.yaml` subtree → expected native config + `source-sha256` stamp) in tests/unit/test_render.py
- [X] T010 [P] [US1] Integration test for install (throwaway venv → components at pins + config_targets stamped; unresolved pin/partial failure exits non-zero and names the component, FR-006) in tests/integration/test_install.py

### Implementation for User Story 1

- [X] T011 [P] [US1] Implement the render engine (jinja2; write to `config_target`; stamp `# mneme-rendered; source-sha256: <hash>; do-not-edit` header) in mneme/render.py (depends on T006)
- [X] T012 [P] [US1] Create per-component jinja2 templates in mneme/templates/ (campaigngenerator.config.yaml.j2, mempalace.yaml.j2, dgxlib.models.yaml.j2, rpg-lib, turbovecdb(-service)) per the config_target paths in the schema contract
- [X] T013 [US1] Implement the installer (create/validate venv; install each component non-editable at its pin via pip/uv shell-out in `order.install`; fail-loud naming) in mneme/install.py (depends on T006)
- [X] T014 [US1] Wire `mneme install` in mneme/cli.py to install.py + render.py; verify installed + rendered before exit 0 (depends on T011, T012, T013)
- [X] T015 [US1] Fill real `pin` (git shas / released versions) + `source` for all six components in mneme.yaml (depends on T013)

> Cross-repo constant removal (gated, one repo per task — the actual re-architecture; breaking changes accepted per 2026-06-24 decision). Each reads from its OWN rendered config (Principle VII), not a mneme import.

- [X] T016 [P] [US1] Replace hardcoded constants in ~/src/CampaignGenerator (extract_facts.py `DEFAULT_ENDPOINT`, prep.py, campaignlib/api/backends.py, config/config.yaml 5etools+rpg-lib) with reads from its rendered config (depends on T012, T014)
- [X] T017 [P] [US1] dgxlib is a SOVEREIGN library (driver for the physical DGX; github.com/kostadis/dgx-fun) — install-only. **Dissolved 2026-06-24:** mneme does not own/render dgxlib's config (removed its config_template/target + template). The DGX endpoint reaches dgxlib from callers (machines.dgx, done in T016); dgxlib's own DEFAULT_ENDPOINT is dgx-fun's concern (their #19).
- [X] T018 [P] [US1] mempalace is mneme-native (internal DB) but ALREADY env-driven. **Reframed 2026-06-24:** no hardcoded infra constants (backend/device via env; turbovec is EMBEDDED not HTTP). mneme adds an `env:` block (option A — exported to managed services on `up`) carrying MEMPALACE_BACKEND; removed the dead config_template/target (mempalace doesn't read ~/.config/mempalace/mempalace.yaml). mempalace worktree untouched. Stored memories = data-plane.
- [X] T019 [P] [US1] rpg-lib (library_api lib + library_server SERVICE) is already CLI/env-driven — port/host/db are CLI args (mneme passes `--port 8000` via the start cmd), the lib dir is `RPG_LIBRARY_ROOT` env. **No hardcoded constants, no rpg-lib code edits.** Removed the dead config_template/target (nothing read rpg_lib.config.yaml) + template; env-wired RPG_LIBRARY_ROOT (commented — set to your value). rpg_lib stays a managed service. (2026-06-24)
- [X] T020 [P] [US1] turbovecdb is mneme-private storage (embedded; mempalace sits on it via connect(path)), **zero hardcoded infra constants** → install-only (removed its config_template/target + template). **turbovecdb-service is NOT mneme's**: the :8077 HTTP layer is llm_wiki's (real consumer: llm_wiki dedup prototype) and really a turbovecdb feature — filed turbovecdb#4. Dropped services.turbovecdb + its startup entry. Both turbovecdb worktrees retired (no edits). (2026-06-24)
- [ ] T021 [US1] Update ~/campaigns/gm-assistant skills to reference workspace paths sourced from `mneme.yaml` (via CampaignGenerator's rendered config), not hardcoded layout (depends on T014)
- [ ] T022 [US1] Grep-verify SC-002 across all six repos: the five constants appear only in config/templates, zero in logic (depends on T016, T017, T018, T019, T020, T021)

**Checkpoint**: MVP — reproducible install works; constants externalized.

---

## Phase 4: User Story 2 - Honest status by tool (Priority: P2)

**Goal**: One command reports observed installed versions + per-service reachability + render
drift, FAILing on any declared-vs-observed contradiction.

**Independent Test**: With the system installed, `mneme status` shows observed-vs-pin and
reachability per service; stop a service or hand-install a wrong version and confirm a FAIL row + exit 1.

### Tests for User Story 2

- [ ] T023 [P] [US2] Unit tests for status (observed-version read; version-drift FAIL; render-drift via stamped-hash mismatch; unreachable-service FAIL; all-PASS→exit 0 / any-FAIL→exit 1) in tests/unit/test_status.py

### Implementation for User Story 2

- [ ] T024 [P] [US2] Implement the health/reachability probe (tcp/http per `service.health`; shared by status and up-gating) in mneme/probe.py (depends on T006)
- [ ] T025 [US2] Implement status (observed version via importlib.metadata / `git rev-parse` vs pin; render-drift via stamped hash; reachability via probe; PASS/FAIL rows; exit 1 on any FAIL) in mneme/status.py (depends on T011, T024)
- [ ] T026 [US2] Wire `mneme status` in mneme/cli.py (table + `--json` rows) (depends on T025)

**Checkpoint**: Status is honest (Principle I); no False Green Dashboard.

---

## Phase 5: User Story 4 - Bring the system up/down in dependency order (Priority: P2)

**Goal**: One command starts managed services in declared order (gating on health), one stops
them; the external DGX endpoint is health-checked, not started.

**Independent Test**: From installed-but-stopped, `mneme up` starts services in `order.startup`
each reachable before dependents (DGX gated first); a failing start exits 1 and names it; `mneme down` stops them.

### Tests for User Story 4

- [ ] T027 [P] [US4] Integration test for lifecycle (up starts managed services in order, gates external DGX reachability first, failed start → exit 1 names service, FR-014; down stops them) in tests/integration/test_lifecycle.py

### Implementation for User Story 4

- [ ] T028 [US4] Implement lifecycle (ordered start of managed services as tracked subprocess + PID/log under ~/.mneme/run/ — disposable, non-authoritative; health-gate each via probe before dependents; external deps health-checked not started; down stops by tracked PID, rediscoverable by probe) in mneme/lifecycle.py (depends on T024)
- [ ] T029 [US4] Wire `mneme up` / `mneme down` in mneme/cli.py (depends on T028)

**Checkpoint**: System comes up/down in declared order; retires `current-setup.md`.

---

## Phase 6: User Story 3 - Change one value, no stale copies (Priority: P3)

**Goal**: Change one `mneme.yaml` value, `mneme apply` re-renders affected configs and
restarts affected managed services so no component runs on a stale copy (Principle V).

**Independent Test**: Change `machines.dgx.endpoint`, `mneme apply`, confirm every derived
config regenerated and no `config_target` or running process retains the old value; status shows no drift.

> Depends on US4 (the restart mechanism in lifecycle.py) and US1 (render.py).

### Tests for User Story 3

- [ ] T030 [P] [US3] Integration test for apply (one-value change → re-render affected config_targets with fresh stamp + restart affected managed services; zero stale copies; status reports no drift; SC-004) in tests/integration/test_apply.py

### Implementation for User Story 3

- [ ] T031 [US3] Implement `mneme apply` (re-render all derived configs; compute affected managed services; restart them via lifecycle; verify no config_target/process retains the prior value) in mneme/cli.py (reusing render.py + lifecycle.py) (depends on T011, T028)

**Checkpoint**: Coherence guarantee proven — the V-over-VII mechanism (re-render + restart) works.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Prove reproducibility in isolation; run the quickstart; document.

- [ ] T032 Complete the SC-005 validation harness — make validation/Dockerfile + docker-compose.yml runnable and add validation/run-validation.sh (the install→up→status→change→apply loop, exit non-zero on any FAIL) (depends on T031)
- [ ] T033 [P] Run quickstart.md Scenarios 1–4 on host; fix any gaps (depends on T031)
- [ ] T034 Run quickstart.md Scenario 5 — clean-container acid test (SC-005) via the harness, DGX_MODE=real AND DGX_MODE=stub (assert honest-unreachable) (depends on T032)
- [ ] T035 [P] Docs: add a `mneme` README (mneme.yaml + CLI usage) and update PLAN.md status (depends on T031)

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

- Every cross-repo edit (T016–T021): component reads its OWN rendered config, never a mneme
  import (VII); no new hardcoded constant introduced (II).
- No task introduces a second authoritative store — no lockfile, no written-back config (V).
- `status` (T025) reads observed state, never echoes `mneme.yaml` (I).

---

## Tracked Fixes (discovered during implementation)

- [X] T036 [US1] Make `~/src/mytools/rpg-lib` pip-installable — add a `pyproject.toml`
  (packaging metadata) so `mneme install` can install it at a pin like the other components.
  **Discovered during the T013 smoke test**: `pip install ~/src/mytools/rpg-lib` fails with
  "Neither 'setup.py' nor 'pyproject.toml' found." Blocks the rpg_lib leg of install and is a
  prerequisite for T019 (rpg-lib reading its rendered config). Until fixed, rpg_lib install
  fails loud (correct behavior, but the component can't be installed). Done in the
  `~/src/platform-refactor/mytools` worktree.

---

## Notes

- [P] = different files/repos, no incomplete-task dependency.
- Commit after each task or logical group; cross-repo edits are gated and reviewed per repo.
- D1 (coherence mechanism) and D2 (DGX external) were ratified 2026-06-24.
- Verify tests fail before implementing.
