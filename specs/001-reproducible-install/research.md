# Phase 0 Research — Reproducible Install & Unified Config

Format per decision: **Decision** / **Rationale** / **Alternatives considered**.
Two decisions are marked **⚠ RATIFY** — they are boundary/precision calls reserved for
the human author (Constitution Principle VIII); the rest are conventional.

---

## D1 — FR-009 coherence mechanism (no stale copies) ⚠ RATIFY

**Decision**: Guarantee coherence by **`platform apply` = re-render all derived configs +
restart the affected managed services**. Editing `platform.yaml` and running `apply` (or
`install`) is the only supported write path. Each rendered file carries a header stamping
the **SHA-256 of the `platform.yaml` subtree it derived from**; `platform status` flags any
rendered file whose stamped hash ≠ the current source as drift (FR-010). Components are
**not** asked to self-validate freshness.

**Rationale**: The spec's lifecycle decision (FR-012, `platform` owns up/down) makes this the
*simplest coordinate* (Principle VIII): coherence falls out of restart rather than needing a
new cache-invalidation subsystem. Restarting a managed service after re-render eliminates the
residual "stale in-memory copy" case the constitution flagged. Keeping validation out of the
components honors low coupling (Principle VII) — they stay ignorant of `platform`. The
hash-stamp is the cheap detector for *out-of-band* edits (someone hand-edits a rendered file or
`platform.yaml` without `apply`), caught by `status` as a FAIL rather than silently used
(Principle I). This is the V-over-VII precedence applied: we force a behavior change in *how
services start* (platform-owned restart), not a new dependency in each component.

**Alternatives considered**:
- *Each component validates its rendered config's hash at startup and refuses to run on
  mismatch* — strongest in-component guarantee, but pushes platform-awareness into every repo
  (couples them to the platform schema; tension with VII). Rejected as the primary mechanism;
  retained conceptually as the `status` drift check, done by the manager instead.
- *Components read `platform.yaml` directly (no render)* — eliminates the cache entirely but
  couples all six components to one schema and makes `platform` non-transient (violates IV).
  Rejected.
- *No restart, rely on file re-render only* — leaves long-running processes on stale in-memory
  config. Rejected (this is exactly the failure the principle forbids).

---

## D2 — DGX-side process scope ⚠ RATIFY

**Decision**: In 001 the **DGX endpoint** (`192.0.2.10:8001`, separate hardware) is an
**external dependency**. `platform up` does **not** start a process on the DGX; it
**health-checks** the endpoint and **orders** local services after confirming it is reachable.
If unreachable at `up`, report it (and fail or warn per the `up` contract), never assume up.

**Rationale**: Remote process management (SSH, remote service control) is a materially larger
surface and a different trust/credential boundary; folding it into 001 would bloat the first
feature. Treating the DGX as a checked external dependency still satisfies the spec (ordered,
honest reachability) and Principle VI (federated — a down external dep yields one FAIL, not a
wedged run). A later feature can add DGX-side lifecycle if wanted.

**Alternatives considered**:
- *`platform` SSHes to the DGX and starts the vLLM/endpoint process* — deferred to a future
  spec; out of scope for a reproducible-install MVP.

---

## D3 — CLI framework

**Decision**: `typer` (Click-based, type-hint native).

**Rationale**: Minimal boilerplate for `install/apply/up/down/status`, good help text, easy
exit-code control (needed for honest non-zero on FAIL, Principle I). Click is the fallback if
a dependency-light footprint is preferred — both acceptable.

**Alternatives**: bare `argparse` (more boilerplate, no real benefit); `click` (fine, slightly
more verbose than typer).

---

## D4 — Config rendering engine

**Decision**: `jinja2` templates, one per component, living in `platform/templates/`, rendered
from the validated `platform.yaml` model into each component's **native** config format
(`config.yaml`, `.env`, `models.yaml`, etc.).

**Rationale**: Components keep their existing native config readers (Principle VII, low
coupling); the manager owns the encoding (Principle VI — logical value → native byte form).
Jinja2 is ubiquitous, golden-file testable, and keeps the rendered output human-inspectable.

**Alternatives**: Python `str.format`/f-strings (fine for trivial files, awkward for nested
YAML); a shared settings library imported by components (rejected — coupling, see D1).

---

## D5 — Version pinning & install execution

**Decision**: Pins live in `platform.yaml` per component as either a released version
(`pin: 3.3.5`) or a git ref (`pin: <sha-or-tag>`) with a `source` (PyPI or a local path / git
URL). `platform install` resolves and installs each into the venv **non-editable at the pin**
(`pip install <pkg>==<ver>` or `pip install git+<url>@<ref>`), in dependency order. Editable
installs (`-e`) are eliminated for in-scope components (kills the silent-drift failure, FR-004).

**Rationale**: Non-editable pinned installs make a `git checkout` in one repo unable to change
another's behavior. Keeping pins in `platform.yaml` (not a lockfile) preserves the single
authority (Principle V); the installed version is then *observed* live by `status`, not stored.

**Alternatives**: `uv` instead of `pip` (faster; acceptable drop-in — record as an
implementation option, not a hard dependency). A generated lockfile (rejected — second
authority, see Complexity Tracking in plan.md).

---

## D6 — Dependency / startup order (the DAG)

**Decision**: Declare both **install order** and **startup order** in `platform.yaml`
(explicit, not inferred). Seed values from the known coupling:
- Install (libs before consumers): `dgxlib` (leaf) → `turbovecdb` → `mempalace` →
  `rpg-lib` → `CampaignGenerator` → `gm-assistant`.
- Startup (services): external `dgx` endpoint reachable first → `turbovecdb-service` (:8077)
  → `rpg-lib` server (:8000) → consumers. `mempalace` with the turbovec backend depends on
  `turbovecdb-service`.

**Rationale**: Explicit declared order = honest, tool-enforced (retires `current-setup.md`
discipline, Principle I/IV). Must be acyclic (Principle VI); validation rejects a cycle.

**Alternatives**: Infer order from import graph (brittle, hidden magic; rejected — declared is
honest and reviewable).

---

## D7 — Service lifecycle implementation (up/down)

**Decision**: `platform up` starts each managed local service as a tracked subprocess (record
PID + log path under a `platform`-owned runtime dir, e.g. `~/.platform/run/`), in declared
order, health-checking each before starting dependents. `platform down` stops them by tracked
PID. The runtime/PID dir is **disposable bookkeeping, not authoritative state** (Principle IV —
on loss, `status` rediscovers liveness by probing; it is not a second source of truth).

**Rationale**: Subprocess+PID is the lowest-friction lifecycle that works in WSL2 without
requiring systemd. Keeping the PID dir non-authoritative avoids a Principle V trap.

**Alternatives**: systemd units (not reliable under WSL2; heavier); a supervisor daemon (a new
long-running manager component — rejected, conflicts with "manager is transient", IV).

---

## D8 — Health / reachability checks

**Decision**: Per-service check declared in `platform.yaml` (default: TCP/HTTP probe of the
service's URL/port; HTTP GET on a known path where one exists, e.g. the DGX `/v1` and
turbovecdb/rpg-lib health routes). `status` and `up` use the same check.

**Rationale**: One definition of "up", used both to gate ordered startup and to report status —
no divergence between what `up` waits for and what `status` reports (Principle I).

---

## D9 — Observed-version reading (for status)

**Decision**: `status` reads each component's installed version from the venv
(`importlib.metadata.version()` for packages; `git rev-parse` in the source dir for
git-pinned local installs) and compares to the `platform.yaml` pin; mismatch = FAIL.

**Rationale**: Observed-from-silicon, never echoed from the declaration (Principle I). No stored
"installed version" file (would be a second authority).

---

## D10 — Containerized validation harness (SC-005 acid test)

**Decision**: A clean container (`validation/Dockerfile` + `validation/docker-compose.yml`
under the feature) is the **canonical SC-005 reproducibility test** and the home for the full
`install → up → status → change-value → apply` integration loop, run in true isolation. The
container is a **proof environment, NOT a deployment target** for 001.

**Rationale**: SC-005 claims one `platform.yaml` reproduces the system on a fresh environment
with no manual edits. A container is the most honest "fresh": no pre-existing `~/.venvs/main`,
no `~/src/*` checkouts, none of the operator discipline that currently *hides* the
fragmentation. If `platform install` brings the system up in a clean container, the
Infrastructure-Proxy constants (II) and Fragmented-State config (III) are *proven*
externalized, not merely appearing to work on a configured box. It also resolves the
port-collision caveat of same-host isolation: the container is its own network namespace, so it
can use the canonical ports (`8000`, `8077`) with zero conflict against live host services.
Composes with (does not replace) git-ref/worktree source isolation: the container gets the
component **sources at their pins**; `platform install` does the rest.

**DGX sub-decision (test both ways — deliberate)**: per D2 the DGX is an external dependency
`platform` health-checks but does not start. Inside the container:
1. **Reach the real DGX** over the network → exercises the real external-dependency path; also
   lets us point `platform.yaml` at a different IP and confirm it follows (this *is* SC-004).
2. **No DGX reachability** → use a stub endpoint, and confirm `status` reports the real one
   **unreachable honestly** (Principle I — no False Green Dashboard) rather than wedging. Worth
   seeing this failure mode on purpose.

**Scope guard**: the container proves reproducibility; it is **not** the install model. 001 is
still "reproducible install on a venv." Containerizing all six components *as the deployment
model* is a different, larger feature (a future `002`) — it must be decided deliberately, not
absorbed into 001 by momentum.

**Alternatives considered**: worktree/second-venv on the same host (good for *source* isolation
but shares the host's env and ports — weaker fresh-environment proof; kept as a complementary
layer, not the acid test); a second physical machine (honest but high-friction; the container
gives the same proof on demand).

## Resolved unknowns summary

All Technical-Context unknowns are resolved above. No blocking `NEEDS CLARIFICATION` remain for
Phase 1. The two ⚠ RATIFY items (D1, D2) carry recommended decisions and proceed under them
unless overridden at review.
