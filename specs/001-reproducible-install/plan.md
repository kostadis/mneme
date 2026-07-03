# Implementation Plan: Reproducible Install & Unified Config

*Reflects the shipped two-command split — `hypostasis` (environment config: install/apply/status) and `mneme` (per-campaign runtime: up/down). See `README.md` for the current command reference.*

**Branch**: `001-reproducible-install` | **Date**: 2026-06-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-reproducible-install/spec.md`

## Summary

Stand up two CLIs in the umbrella repo — `hypostasis` (environment config) and `mneme`
(per-campaign runtime) — that turn the campaign/DGX system into a reproducibly-installable,
single-source-of-truth system. One hand-edited `hypostasis.yaml` is the sole authority for
config/wiring (endpoints, ports, paths, venv, version pins).

- `hypostasis install` — create/validate the venv, install each in-scope component at its
  pinned version, and **render** each component's native config/env from `hypostasis.yaml`
  (no shared import forced into components).
- `hypostasis apply` — re-render derived configs after a `hypostasis.yaml` change, stamping
  each with a fresh source hash so `status` can detect drift. There is no local managed
  service for `apply` to restart — the DGX endpoint and rpg-lib are external substrate
  `hypostasis` never starts.
- `hypostasis status` — report each component's *observed installed* version + per-service
  reachability, and flag any declared-vs-observed or render drift as a failure.
- `mneme up <campaign>` / `mneme down <campaign>` — launch/stop that campaign's
  CampaignGenerator instance on the hypostasis-configured environment (health-gated against
  the DGX endpoint and rpg-lib, both external substrate `mneme` checks but never starts).

The coherence guarantee (Principle V, no stale copies) is regenerate-on-apply +
hash-stamp drift detection: `hypostasis apply` re-renders every derived config from the
current `hypostasis.yaml` and stamps it with a source hash; `status` reports any rendered
file whose stamp no longer matches as drift. There is no local managed-service restart step —
the DGX endpoint and rpg-lib are external substrate, and the one process either tool runs
(the per-campaign CampaignGenerator instance) is `mneme`'s, started fresh on
`mneme up <campaign>` rather than restarted in place by `apply`.

## Technical Context

**Language/Version**: Python 3.11+ (matches the existing ecosystem — every component is
Python; `~/.venvs/main` is the shared runtime).

**Primary Dependencies**: standard-library-first. `PyYAML` (read `hypostasis.yaml`),
`jinja2` (render component configs from templates), `click` or `typer` (CLI),
`httpx`/stdlib for reachability checks, `packaging` for version resolution. Install/pin
execution shells out to `pip`/`uv` against the venv. No database.

**Storage**: `hypostasis.yaml` — the single authoritative file. Derived/rendered component
configs are non-authoritative regenerated outputs. **No lockfile and no second store**
(observed/resolved state is read live from the venv, never persisted as a competing
authority — that would violate Principle V).

**Testing**: `pytest`. Unit tests for render (golden-file: `hypostasis.yaml` → expected
native config), schema validation, drift detection. The full install→up→status→change-value
→apply integration loop runs in a **clean container** (`validation/`) — the canonical SC-005
reproducibility acid test (research D10): a fresh environment with no pre-existing venv/checkouts
proves the constants are genuinely externalized, not a configured-box illusion. The container is
a **proof environment, not a deployment target** (deployment-as-containers would be a future 002).

**Target Platform**: Linux / WSL2 (the dev box) and a second Linux machine for the
reproducibility check (SC-005). The DGX endpoint is remote (separate hardware).

**Project Type**: Two-package single repo — `hypostasis/` (environment-config CLI) +
`mneme/` (per-campaign runtime CLI), plus per-component config templates under
`hypostasis/templates/`. It edits the *other* repos during `/speckit.implement` (replace
hardcoded constants with values read from each component's own rendered config).

**Performance Goals**: not a hot path. `status` should answer in a couple of seconds;
`install` is bounded by `pip`. No throughput targets.

**Constraints**: must run from the existing venv model; must not introduce a second
authoritative store; cross-repo edits must be gated task-by-task; components keep reading
their own native config (low coupling, Principle VII).

**Scale/Scope**: 6 components, ~3 managed/checked services, one operator. Single-machine
deployments, occasionally reproduced on a second machine.

### Ratified decisions (see research.md) — ✅ both ratified 2026-06-24

1. **FR-009 coherence mechanism** → **re-render-on-`apply` + a source-hash header** on each
   rendered file so `status` detects out-of-band drift, as the guarantee. Components are
   *not* asked to self-validate (keeps coupling low; V-over-VII). There is no local managed
   service for `apply` to restart (DGX/rpg-lib are external substrate); the accepted
   limitation is that out-of-band consumers are caught reactively by `status`, not prevented.
2. **DGX-side process scope** → the DGX endpoint is an **external dependency** `mneme`
   health-checks and orders against — `mneme` does **not** start a process on the DGX in
   001 (no SSH/remote process management). Deferrable to a later feature.

## Constitution Check

*GATE: must pass before Phase 0. Re-checked after Phase 1 design (below).*

| Principle | Gate | This plan |
|---|---|---|
| I — Silicon Truth | `status` reports observed, never declared | ✅ `status` reads installed version from the venv + live reachability; render drift detected by hash. Install fails loudly on partial/unverified result. |
| II — Sovereign Identity / no Infra Proxy | no hardcoded IP/port/path in component logic | ✅ All five constants move to `hypostasis.yaml`; implement replaces them with reads from each component's rendered config. |
| III — Intrinsic State / no Horcruxes | no orphaned/hand-synced side state | ✅ One authority; derived configs are regenerated, never hand-edited; no parallel truth. |
| IV — Manager is a Transient Viewer | delete `hypostasis`, components still run; reinstall reconstructs | ✅ Components run from their own rendered config without `hypostasis` present; `install` reconstructs wiring from `hypostasis.yaml`. No irreplaceable state in the manager. |
| V — One Entity, One DB / no stale copies | single authority; coherent caches | ✅ `hypostasis.yaml` is the sole authority; `apply` re-renders + hash-stamps every derived config so drift is detected, not silently tolerated. **No lockfile** (would be a 2nd authority). |
| VI — Federated Authority, input[∞] | per-component, degrade independently; acyclic deps | ✅ install/status/up operate per-component; one unreachable service = one FAIL, not a wedged run; dependency order declared and acyclic (leaf `dgxlib` first). |
| VII — Logical Datasets / low coupling | components consume meanings, not encodings; render not import | ✅ Render into each component's native config; no shared `mneme` import forced in. Subordinate to V per precedence. |
| VIII — Transform the Constraint | simpler coordinate before complexity | ✅ Reuse each component's *existing* native config as the injection point (no new runtime); coherence falls out of regenerate-on-apply + hash-stamp drift detection rather than a new cache-invalidation subsystem. |

**Precedence applied (V over VII):** the coherence guarantee is met by `hypostasis` owning
regenerate-on-apply + hash-stamp drift detection (V), not by preserving any component's
independent store; components are edited where needed (the 2026-06-24 "breaking changes
accepted" decision). No unjustified violations → **GATE PASS**.

**Anti-patterns checked:** Optimistic Lies (status reads silicon — avoided), Infrastructure
Proxy (constants externalized — avoided), Fragmented State (single authority — avoided),
Split-Brain (no second authoritative store, regenerate-and-hash-stamp-on-apply — avoided).

## Project Structure

### Documentation (this feature)

```text
specs/001-reproducible-install/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions + rationale
├── data-model.md        # Phase 1 — hypostasis.yaml schema + entities
├── quickstart.md        # Phase 1 — runnable validation scenarios (maps to SC-001..006)
├── contracts/
│   ├── cli.md           # hypostasis install/apply/status + mneme up/down command contract
│   └── hypostasis-yaml.schema.md  # the authoritative config schema
├── validation/          # SC-005 acid test — clean-container proof env (Dockerfile, compose, README)
└── tasks.md             # Phase 2 — /speckit.tasks (NOT created here)
```

### Source Code (repository root)

```text
hypostasis/                 # environment-config CLI (install/apply/status)
├── __init__.py
├── cli.py                     # install / apply / status entrypoints
├── config.py                  # load + validate hypostasis.yaml (the single authority)
├── models.py                  # ConfigEntity, Machine, Service, Component, DerivedConfig
├── install.py                 # venv + pinned installs in dependency order
├── render.py                  # render derived component configs (jinja2), stamp source hash
├── probe.py                   # tcp/http reachability probe (shared by status)
├── status.py                  # observed version + reachability + drift detection
└── templates/                 # native-config templates
    └── campaigngenerator.wiring.yaml.j2

mneme/                       # per-campaign runtime CLI (integrate/up/down/mp)
├── __init__.py
├── cli.py                     # integrate / up / down entrypoints
├── lifecycle.py               # up/down: health-gate substrate + mempalace, start/stop
│                               # one campaign's CampaignGenerator
├── mcp/                        # advisory MCP server
├── mempalace/                  # `mneme mp` — per-campaign mempalace management (002/003)
└── recipes/                    # the shared mempalace recipe mneme owns

hypostasis.example.yaml      # template for the real ~/.config/hypostasis/hypostasis.yaml
                              # (never committed — the deployed file lives outside the repo)

tests/
├── unit/                      # render golden-files, schema validation, drift detection,
│                               # lifecycle
└── integration/               # install/apply/status loop (validation/ harness)

# pyproject.toml exposes two console_scripts from this one repo:
#   hypostasis = "hypostasis.cli:app"
#   mneme = "mneme.cli:app"

# Cross-repo (edited during /speckit.implement, gated per task):
#   ~/src/CampaignGenerator — replace hardcoded constants with reads from its own
#   (now rendered) config.
```

**Structure Decision**: Two packages, one repo. `hypostasis/` configures the environment —
install/render/status — and is *transient* (Principle IV): delete it, components still run
from rendered config; reinstall reconstructs. `mneme/` is the per-campaign runtime, started
fresh for each campaign session; it holds no authoritative state either. The only authority
is `hypostasis.yaml`. Per-component templates live under `hypostasis/templates/` (the
environment manager owns the encoding, Principle VII), not in the component repos.

## Complexity Tracking

> No Constitution Check violations to justify. Two deliberate choices worth recording:

| Choice | Why | Simpler/other alternative rejected because |
|---|---|---|
| No lockfile; pins live only in `hypostasis.yaml`; observed state read live | A lockfile would be a second store of the same truth → Principle V violation (split-brain on restore) | A lockfile "for reproducibility" is unnecessary: pins are already exact in the one authority; reproducibility comes from the authority + live verification, not a parallel file. |
| Render into native config (not a shared `mneme` import) | Lowest coupling; components stay ignorant of `mneme` (IV, VII) | A shared runtime import would couple every component to the mneme schema and make `mneme` non-transient. |
