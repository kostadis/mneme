# Feature Specification: Reproducible Install & Unified Config

**Feature Branch**: `001-reproducible-install`

**Created**: 2026-06-24

**Status**: Draft — clarifications resolved 2026-06-24 (scope: all six components; `platform` owns service lifecycle)

**Input**: Re-architect the integration plane of the campaign/DGX system so the
whole thing installs reproducibly from one source of truth, eliminating the
hand-maintained constants, scattered config, and editable-install drift that make
"is it installed correctly and running?" a question of operator discipline rather
than a question a tool can answer.

## Why (problem this solves)

The ~6 components (dgxlib, mempalace, turbovecdb + service, CampaignGenerator,
rpg-lib, gm-assistant) each work in isolation. The pain is entirely in the
integration plane: infrastructure identity is hardcoded into component logic
(`192.0.2.10:8001`, `~/src/5etools-kostadis/data`, `localhost:8000`, port `8077`,
`~/.venvs/main`); there is no system-level config (each tool keeps its own
hand-maintained file + env vars); versions are unpinned and editable-installs let a
`git checkout` in one repo silently change another's behavior; and "is it up?" is
answered by a `current-setup.md` discipline doc, not a tool. This is **Fragmented
State** + **Infrastructure Proxy** in the project's own doctrine. The decision of
record (2026-06-24) is that this fragmentation is a bug to remove, not a
compatibility surface to preserve — breaking component changes are accepted.

## User Scenarios & Testing *(mandatory)*

The "user" here is the operator (Kostadis) standing the system up, upgrading it, or
moving it to a second machine.

### User Story 1 - Reproducible install from one source of truth (Priority: P1)

The operator edits a single `platform.yaml`, runs one install command, and the whole
system comes up on a fresh virtual environment — every component installed at its
pinned version, every component's own config/env populated from `platform.yaml` —
with **no manual path/IP/port edits anywhere else**.

**Why this priority**: This is the core of the feature and the MVP. If only this
ships, the system is already reproducible and the hardcoded-constant / scattered-config
pain (the bulk of the problem) is gone. Everything else builds on the single
authority this establishes.

**Independent Test**: On a clean venv (or a second machine), with only `platform.yaml`
edited for that environment, run the install and confirm the system is usable without
touching any component's own config or source.

**Acceptance Scenarios**:

1. **Given** a fresh venv and a filled-in `platform.yaml`, **When** the operator runs
   the install, **Then** every in-scope component is installed at its pinned version
   and its native config/env is populated from `platform.yaml`, with no further manual
   edits required.
2. **Given** a working install, **When** the operator greps the component repos for the
   previously-hardcoded constants (`192.0.2.10`, `5etools-kostadis/data`,
   `localhost:8000`, `8077`, `.venvs/main`), **Then** matches appear only in
   config/templates sourced from `platform.yaml`, never in component logic.
3. **Given** an install run where a component source or pinned version cannot be
   resolved, **When** the install proceeds, **Then** it fails loudly and names the
   unresolved component, rather than partially completing and reporting success.

---

### User Story 2 - Honest status by tool, not by discipline (Priority: P2)

The operator runs one status command and gets the truth: which components are
installed, at which **actually-installed** versions, and whether each service is
reachable — replacing the `current-setup.md` discipline doc.

**Why this priority**: Turns "is it up and correct?" from tribal knowledge into a
verifiable answer. Depends on P1 (there must be a declared truth to check observed
state against), but is independently valuable and independently testable.

**Independent Test**: With the system installed, run status and confirm it reports
observed installed versions + a per-service reachability check; then stop a service
and confirm status reports it as down.

**Acceptance Scenarios**:

1. **Given** an installed system, **When** the operator runs status, **Then** it reports
   each in-scope component's *observed installed* version and a reachability result per
   service.
2. **Given** a component whose installed version no longer matches its `platform.yaml`
   pin, **When** the operator runs status, **Then** that drift is reported as a failure,
   not a pass (no False Green Dashboard).
3. **Given** a service that is not running, **When** the operator runs status, **Then**
   it is reported as unreachable rather than assumed up.

---

### User Story 3 - Change one value, everything follows — no stale copies (Priority: P3)

The operator changes a single value in `platform.yaml` (e.g. the DGX IP), re-applies,
and every component picks up the new value. No component is left running on a stale
cached/rendered copy of the old value.

**Why this priority**: This is the live-time half of the single-authority guarantee
(Constitution Principle V). It prevents the "I changed it via the CLI but tool X had a
cached copy and broke" failure. Lower priority only because it builds on P1's rendering
mechanism; the coherence guarantee is non-negotiable once rendering exists.

**Independent Test**: Change the DGX endpoint in `platform.yaml` only, re-apply, and
confirm every component now uses the new endpoint and none reads the old one.

**Acceptance Scenarios**:

1. **Given** an installed system, **When** the operator changes a value in `platform.yaml`
   and re-applies, **Then** every derived component config is regenerated and no component
   continues to use the prior value.
2. **Given** a derived component config that has drifted from `platform.yaml` (edited out
   of band, or not re-rendered after a change), **When** status runs, **Then** the
   staleness is detected and reported rather than silently tolerated.

---

### User Story 4 - Bring the system up and down in dependency order (Priority: P2)

After install, the operator runs one command to bring the system **up** — `platform`
starts every service in declared dependency order — and one command to bring it **down**.
The undocumented "what must be running, and in what order" knowledge in `current-setup.md`
becomes a declared, tool-enforced order.

**Why this priority**: Install (P1) produces an installed system; this makes it a *running*
system without operator-held startup choreography. It directly retires the "implicit venv +
startup order" pain. Builds on P1 (there must be installed components to start).

**Independent Test**: From an installed-but-stopped system, run bring-up and confirm all
services come up in order and pass reachability; run bring-down and confirm they stop.

**Acceptance Scenarios**:

1. **Given** an installed system, **When** the operator runs bring-up, **Then** services start
   in the declared dependency order and each is confirmed reachable before dependents start.
2. **Given** a service that fails to start, **When** bring-up runs, **Then** it reports the
   failure and names the service, rather than reporting the system up.
3. **Given** a running system, **When** the operator runs bring-down, **Then** the services
   `platform` manages are stopped.

---

### Edge Cases

- **Partial install failure**: a component fails mid-install — the run reports failure and
  what completed; it never reports overall success on a partial result (Principle I).
- **Declared-vs-installed version drift**: `platform.yaml` pins version X, the venv has Y —
  reported as a failure by status.
- **Stale render**: `platform.yaml` changed but a component's derived config was not
  regenerated — detected (e.g. source-hash mismatch) and reported, not silently used.
- **Service down at status time**: reported unreachable, not assumed up.
- **Unresolvable pin/source**: a git sha/tag/version or a component source path that does
  not exist — fail loudly and name it.
- **Second machine / fresh venv**: only `platform.yaml` differs for the new environment;
  no per-component edits needed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST have exactly one authoritative, hand-edited source of truth
  for the system's config/wiring (`platform.yaml`): endpoints, ports, paths, the venv,
  and component version pins. No second hand-maintained store of this config may exist.
- **FR-002**: All previously-hardcoded infrastructure constants MUST be sourced from
  `platform.yaml` and MUST NOT appear in component logic. At minimum: the DGX endpoint and
  default model, the 5etools data root, the rpg-lib URL and directory, the
  turbovecdb-service URL/port, and the venv location.
- **FR-003**: A single install action MUST, from `platform.yaml`: create/validate the venv;
  install each in-scope component at its pinned version in declared dependency order; and
  populate each component's own native config/env from `platform.yaml`.
- **FR-004**: Component versions MUST be pinned (git sha/tag or released version) so that a
  `git checkout` or upstream change in one repo cannot silently alter another's behavior.
  Editable-install drift MUST be eliminated for in-scope components.
- **FR-005**: The install MUST be reproducible: the same `platform.yaml` on a fresh venv (or
  a second machine) MUST bring up an equivalent system with no manual path/IP/port edits.
- **FR-006**: The install MUST fail loudly and name the offending component when a pin or
  source cannot be resolved, or when a step fails — it MUST NOT report success on a partial
  or unverified result.
- **FR-007**: A single status action MUST report, per in-scope component, the *observed
  installed* version and a per-service reachability/health result — derived from the live
  system, never echoed back from `platform.yaml`'s declarations.
- **FR-008**: Status MUST report as a failure (not a pass) any case where observed state
  contradicts declared state: installed version ≠ pinned version, or a service that should
  be up is unreachable.
- **FR-009**: Derived/rendered component configs are non-authoritative copies and MUST be
  kept coherent with `platform.yaml`: after a change to `platform.yaml`, no component may
  continue to operate on a stale copy. Changing a value through the single supported write
  path MUST NOT be able to leave any component on a stale rendered value. *(The mechanism —
  re-render-on-apply, restart/reload of affected components, source-hash freshness checks,
  or a combination — is a `/speckit.plan` decision; this requirement fixes the guaranteed
  behavior, not the implementation.)*
- **FR-010**: Status MUST detect and report a derived config that has drifted from
  `platform.yaml` (e.g. changed but not re-rendered), rather than silently tolerating it.
- **FR-011** *(resolved 2026-06-24)*: The in-scope component set for this feature is **all
  six**: dgxlib, mempalace, turbovecdb (+ turbovecdb-service), CampaignGenerator, rpg-lib,
  and gm-assistant. 001 delivers one reproducible install of the whole system, not a slice.
- **FR-012** *(resolved 2026-06-24)*: `platform` MUST own service **lifecycle**. A single
  bring-up action MUST start the system's services (rpg-lib server, turbovecdb-service, and
  any other declared service) in declared dependency order, and a bring-down action MUST stop
  them. The dependency/startup order is declared in `platform.yaml`, not held as operator
  tribal knowledge. (The DGX endpoint, if it runs on separate hardware, MAY be a depended-upon
  external service that `platform` reachability-checks rather than starts — see Assumptions.)
- **FR-013**: After install + bring-up from a filled-in `platform.yaml`, the system MUST reach
  a running state with **no** manual service-start steps outside `platform`.
- **FR-014**: Bring-up MUST be ordering-correct and honest: a service whose dependency is not
  yet healthy MUST NOT be reported as up, and a failure to start MUST be reported loudly
  (Principle I — no False Green Dashboard), naming the service that failed.

### Key Entities

- **Config/wiring entity** — the single entity this feature governs. Its authoritative store
  is `platform.yaml`. Attributes: machines/endpoints, data roots, service URLs/ports, venv,
  and per-component version pins + source. (Constitution Principle V applies: one authority.)
- **Component** — an installable unit (a repo or package) with a name, a source, a pinned
  version, a place in the dependency order, and a native config/env that the installer
  populates from the config entity.
- **Service** — a running endpoint a component exposes or depends on (DGX endpoint, rpg-lib,
  turbovecdb-service) that `platform` starts/stops (per FR-012) and status reachability-checks.
  Carries a declared place in the startup dependency order.
- **Derived config** — a non-authoritative, regenerated-from-`platform.yaml` copy of a
  component's native config. Never hand-edited; kept coherent with the authority.
- **Out-of-scope (named to bound the feature): data-plane entities** — mempalace's vector
  store, turbovecdb's stored vectors, and the campaign/5etools *data* roots' contents. Each
  is its own entity that already owns its truth; `platform.yaml` *references where they live*
  (a path/endpoint — config) without *containing their contents*. This feature does not move,
  centralize, or own data-plane state.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a single edited `platform.yaml` on a fresh venv, one install command brings
  the in-scope system up with **zero** manual path/IP/port edits elsewhere.
- **SC-002**: Grep of the in-scope component repos for the five hardcoded constants returns
  **zero** matches in logic (only config/template references sourced from `platform.yaml`).
- **SC-003**: One status command reports observed installed version + reachability for **every**
  in-scope component/service, and reports any declared-vs-observed drift as a failure.
- **SC-004**: Changing exactly one value in `platform.yaml` (e.g. the DGX IP) and re-applying
  causes **100%** of in-scope components to use the new value, with **zero** left on the old
  value (verified by status showing no drift and no component reaching the old endpoint).
- **SC-005**: Reproducibility — the same `platform.yaml` produces an equivalent working system
  on a second venv/machine, demonstrated at least once.
- **SC-006**: From an installed system, one bring-up command starts **all** of the system's
  managed services in correct dependency order and they pass reachability; one bring-down
  command stops them — with **zero** manual service-start steps outside `platform`.

## Assumptions

- `platform.yaml` is hand-edited as a file; the file itself is the single write path, and an
  apply/install action re-renders derived configs from it. (Not assuming a separate
  `platform config set` CLI; revisit if FR-012 implies it.)
- Component repos are local checkouts under `~/src` (and selected PyPI packages), as today.
- Breaking changes to component repos (replacing hardcoded constants with config-sourced
  values, collapsing a component-local *config* store into `platform.yaml`) are accepted per
  the 2026-06-24 decision — components are not held immutable.
- The venv model (`~/.venvs/main`) remains the runtime; its *location* becomes a `platform.yaml`
  value rather than a hardcoded assumption.
- `platform` owns the lifecycle of services it can start locally (rpg-lib server,
  turbovecdb-service). The DGX endpoint, when it runs on separate hardware (`192.0.2.10`), is
  treated as an external dependency `platform` reachability-checks and orders against, not a
  process it starts — confirm during `/speckit.plan` whether any DGX-side process is in scope.
- Spec Kit drives the build (`/speckit.plan` → `/speckit.tasks` → `/speckit.implement`); the
  cross-repo edits that implement FR-002/FR-004 are gated task by task.

## Constitution Alignment

This feature is the first application of the constitution; each principle has a concrete hook
here: single authority + no stale copies (**V**) is `platform.yaml` + coherent renders;
no Infrastructure Proxy (**II**) is FR-002; observed-not-declared status (**I**) is FR-007/008;
manager-is-a-transient-viewer (**IV**) is "delete platform, components still run from rendered
config; reinstall reconstructs from `platform.yaml`"; render-into-native-config for low coupling
(**VII**) is the default mechanism, subordinate to V per the V-over-VII precedence rule.

## Clarifications

### Session 2026-06-24
- **FR-011 — component scope of 001** → **All six components** (dgxlib, mempalace,
  turbovecdb(+service), CampaignGenerator, rpg-lib, gm-assistant). One reproducible install of
  the whole system, not a vertical slice.
- **FR-012 — service lifecycle** → **`platform` owns lifecycle**: `up` starts services in
  declared dependency order, `down` stops them; order lives in `platform.yaml`. (DGX endpoint
  on separate hardware is an external dependency to order/health-check, not start — confirm in
  `/speckit.plan`.)

No open clarifications remain. One item is intentionally deferred to `/speckit.plan` (HOW, not a
spec gap): FR-009's cache-coherence *mechanism* (re-render-on-apply / restart / source-hash check).
