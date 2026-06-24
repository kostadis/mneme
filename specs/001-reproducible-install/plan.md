# Implementation Plan: Reproducible Install & Unified Config

**Branch**: `001-reproducible-install` | **Date**: 2026-06-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-reproducible-install/spec.md`

## Summary

Stand up a `platform` CLI in the umbrella repo that turns the campaign/DGX system into
a reproducibly-installable, single-source-of-truth system. One hand-edited
`platform.yaml` is the sole authority for config/wiring (endpoints, ports, paths, venv,
version pins, dependency/startup order). The CLI:

- `platform install` — create/validate the venv, install all six components at pinned
  versions in dependency order, and **render** each component's native config/env from
  `platform.yaml` (no shared import forced into components).
- `platform apply` — re-render derived configs after a `platform.yaml` change and
  restart affected managed services, guaranteeing no component runs on a stale copy.
- `platform up` / `platform down` — start/stop managed services in declared dependency
  order (external DGX endpoint is health-checked and ordered against, not started).
- `platform status` — report each component's *observed installed* version + per-service
  reachability, and flag any declared-vs-observed or render drift as a failure.

The coherence guarantee (Principle V, no stale copies) falls out of the lifecycle
ownership chosen in the spec: because `platform` owns service start/stop, `apply` can
re-render **and restart**, so no managed process keeps stale in-memory config; a
source-hash header on each rendered file lets `status` detect out-of-band drift.

## Technical Context

**Language/Version**: Python 3.11+ (matches the existing ecosystem — every component is
Python; `~/.venvs/main` is the shared runtime).

**Primary Dependencies**: standard-library-first. `PyYAML` (read `platform.yaml`),
`jinja2` (render component configs from templates), `click` or `typer` (CLI),
`httpx`/stdlib for reachability checks, `packaging` for version resolution. Install/pin
execution shells out to `pip`/`uv` against the venv. No database.

**Storage**: `platform.yaml` — the single authoritative file. Derived/rendered component
configs are non-authoritative regenerated outputs. **No lockfile and no second store**
(observed/resolved state is read live from the venv, never persisted as a competing
authority — that would violate Principle V).

**Testing**: `pytest`. Unit tests for render (golden-file: `platform.yaml` → expected
native config), schema validation, drift detection. The full install→up→status→change-value
→apply integration loop runs in a **clean container** (`validation/`) — the canonical SC-005
reproducibility acid test (research D10): a fresh environment with no pre-existing venv/checkouts
proves the constants are genuinely externalized, not a configured-box illusion. The container is
a **proof environment, not a deployment target** (deployment-as-containers would be a future 002).

**Target Platform**: Linux / WSL2 (the dev box) and a second Linux machine for the
reproducibility check (SC-005). The DGX endpoint is remote (separate hardware).

**Project Type**: Single project — a CLI tool (`platform/` package) plus per-component
config templates. It edits the *other* repos during `/speckit.implement` (replace
hardcoded constants with values read from each component's own rendered config).

**Performance Goals**: not a hot path. `status` should answer in a couple of seconds;
`install` is bounded by `pip`. No throughput targets.

**Constraints**: must run from the existing venv model; must not introduce a second
authoritative store; cross-repo edits must be gated task-by-task; components keep reading
their own native config (low coupling, Principle VII).

**Scale/Scope**: 6 components, ~3 managed/checked services, one operator. Single-machine
deployments, occasionally reproduced on a second machine.

### Decisions needing your ratification (see research.md)

1. **FR-009 coherence mechanism** → proposed: **re-render-on-`apply` + restart affected
   managed services** as the guarantee, with a **source-hash header** on each rendered
   file so `status` detects out-of-band drift. Components are *not* asked to self-validate
   (keeps coupling low). ⚠ Ratify: this is the V-vs-VII boundary call.
2. **DGX-side process scope** → proposed: the DGX endpoint is an **external dependency**
   `platform` health-checks and orders against — `platform` does **not** start a process on
   the DGX in 001 (no SSH/remote process management). ⚠ Ratify.

## Constitution Check

*GATE: must pass before Phase 0. Re-checked after Phase 1 design (below).*

| Principle | Gate | This plan |
|---|---|---|
| I — Silicon Truth | `status` reports observed, never declared | ✅ `status` reads installed version from the venv + live reachability; render drift detected by hash. Install fails loudly on partial/unverified result. |
| II — Sovereign Identity / no Infra Proxy | no hardcoded IP/port/path in component logic | ✅ All five constants move to `platform.yaml`; implement replaces them with reads from each component's rendered config. |
| III — Intrinsic State / no Horcruxes | no orphaned/hand-synced side state | ✅ One authority; derived configs are regenerated, never hand-edited; no parallel truth. |
| IV — Manager is a Transient Viewer | delete `platform`, components still run; reinstall reconstructs | ✅ Components run from their own rendered config without `platform` present; `install` reconstructs wiring from `platform.yaml`. No irreplaceable state in the manager. |
| V — One Entity, One DB / no stale copies | single authority; coherent caches | ✅ `platform.yaml` is the sole authority; `apply` re-renders + restarts so no stale in-memory copy; hash-header drift detection. **No lockfile** (would be a 2nd authority). |
| VI — Federated Authority, input[∞] | per-component, degrade independently; acyclic deps | ✅ install/status/up operate per-component; one unreachable service = one FAIL, not a wedged run; dependency order declared and acyclic (leaf `dgxlib` first). |
| VII — Logical Datasets / low coupling | components consume meanings, not encodings; render not import | ✅ Render into each component's native config; no shared `platform` import forced in. Subordinate to V per precedence. |
| VIII — Transform the Constraint | simpler coordinate before complexity | ✅ Reuse each component's *existing* native config as the injection point (no new runtime); lifecycle ownership makes coherence fall out of restart rather than a new cache-invalidation subsystem. |

**Precedence applied (V over VII):** the coherence guarantee is met by `platform` owning
re-render+restart (V), not by preserving any component's independent store; components are
edited where needed (the 2026-06-24 "breaking changes accepted" decision). No unjustified
violations → **GATE PASS**.

**Anti-patterns checked:** Optimistic Lies (status reads silicon — avoided), Infrastructure
Proxy (constants externalized — avoided), Fragmented State (single authority — avoided),
Split-Brain (no second authoritative store, restart-on-apply — avoided).

## Project Structure

### Documentation (this feature)

```text
specs/001-reproducible-install/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions + rationale
├── data-model.md        # Phase 1 — platform.yaml schema + entities
├── quickstart.md        # Phase 1 — runnable validation scenarios (maps to SC-001..006)
├── contracts/
│   ├── cli.md           # platform install/apply/up/down/status command contract
│   └── platform-yaml.schema.md  # the authoritative config schema
├── validation/          # SC-005 acid test — clean-container proof env (Dockerfile, compose, README)
└── tasks.md             # Phase 2 — /speckit.tasks (NOT created here)
```

### Source Code (repository root)

```text
platform/                      # the CLI package (the manager — transient viewer)
├── __init__.py
├── cli.py                     # install / apply / up / down / status entrypoints
├── config.py                  # load + validate platform.yaml (the single authority)
├── render.py                  # render derived component configs (jinja2), stamp source hash
├── install.py                 # venv + pinned installs in dependency order
├── lifecycle.py               # up/down: ordered start/stop of managed services
├── status.py                  # observed version + reachability + drift detection
└── templates/                 # one native-config template per component
    ├── campaigngenerator.config.yaml.j2
    ├── mempalace.yaml.j2
    ├── dgxlib.models.yaml.j2
    └── ...                     # rpg-lib, turbovecdb(-service), gm-assistant

platform.yaml                  # THE single authority (repo root; hand-edited)

tests/
├── unit/                      # render golden-files, schema validation, drift detection
└── integration/               # full install→up→status→apply loop on a throwaway venv

# Cross-repo (edited during /speckit.implement, gated per task):
#   ~/src/CampaignGenerator, ~/src/dgx, ~/src/mempalace, ~/src/mytools(rpg-lib),
#   ~/src/turbovecdb(-service) — replace hardcoded constants with reads from each
#   component's own (now rendered) config.
```

**Structure Decision**: Single-project CLI. The `platform/` package is the manager; it
is *transient* (Principle IV) — it installs, renders, starts, and reports, but holds no
authoritative state itself. The only authority is `platform.yaml` at the repo root.
Per-component templates live with the manager (it owns the encoding, Principle VII), not
in the component repos.

## Complexity Tracking

> No Constitution Check violations to justify. Two deliberate choices worth recording:

| Choice | Why | Simpler/other alternative rejected because |
|---|---|---|
| No lockfile; pins live only in `platform.yaml`; observed state read live | A lockfile would be a second store of the same truth → Principle V violation (split-brain on restore) | A lockfile "for reproducibility" is unnecessary: pins are already exact in the one authority; reproducibility comes from the authority + live verification, not a parallel file. |
| Render into native config (not a shared `platform` import) | Lowest coupling; components stay ignorant of `platform` (IV, VII) | A shared runtime import would couple every component to the platform schema and make `platform` non-transient. |
