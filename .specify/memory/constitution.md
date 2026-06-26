<!--
SYNC IMPACT REPORT — constitution amendment 2026-06-26
Version: 1.0.0 → 1.1.0  (MINOR — a new principle added)
Added principle: IX. Observability (State and To-Do are Discoverable, not Remembered)
Added anti-pattern: Opacity / Tribal State (preamble list + Governance list)
Modified: Governance — principle-test range "I–VIII" → "I–IX"; "four anti-patterns" → "five"
Rationale: GH #11 (was local issue 0008). Principle I governs the HONESTY of a chosen
  report; IX governs its COMPLETENESS/DISCOVERABILITY — a distinct concern, hence a new
  principle rather than an expansion of I. Worked example: the proposal-aware `mneme mp
  status` to-do shipped in feature 002 (GH #14).
Templates / docs checked for sync:
  ✅ plan-template.md — Constitution Check is generic ("[Gates determined based on
     constitution file]"); auto-applies IX, no edit needed.
  ✅ spec-template.md — does not enumerate principles; no change.
  ✅ tasks-template.md — does not enumerate principles; no change.
  ✅ CLAUDE.md (project) — points to the constitution, does not enumerate; no change.
Follow-up: close GH #11 once ratified.
-->
# Platform Constitution

> Encodes the Kostadis architectural doctrine — distilled from the Kostadis Engine
> lenses (L1 Tribunal, L2 Anti-Gravity, L3 Lagrange, L4 Value-Bridge) — as the
> governing principles for `~/src/mneme`, the umbrella repo that owns the
> integration / distribution / orchestration plane of the campaign/DGX system.
>
> The principles are general (they are how Kostadis judges any system). Each one
> carries an **On this platform** clause that binds it to the concrete work here.
> Every principle names the doctrine anti-pattern it exists to kill:
> **Optimistic Lies**, **Infrastructure Proxy**, **Fragmented State**, **Split-Brain**,
> **Opacity / Tribal State**.

## Core Principles

### I. Silicon Truth over Software Ack
The source of truth is the physical/observed state of the system, never a cached
representation of it. A diagram, a dashboard, a returned `200`, or a value in a
manager's database is a *claim*, not the truth. "Success" means the change was
confirmed where it actually lives — the disk wrote, the service answered, the
version is the version on the venv — not that a function returned without error.
Tooling MUST distinguish a software ack ("looks good") from a confirmed state, and
MUST resolve disagreements in favor of the silicon.
- **Kills:** Optimistic Lies (the False Green Dashboard).
- **On this platform:** `platform status` reports *observed* state — it health-checks
  each service and reads the *installed* version, never echoes back what
  `platform.yaml` declared. A declared pin and an installed package that disagree
  is a FAIL surfaced to the human, not a green checkmark.

### II. Sovereign Identity (no Infrastructure Proxy)
An object's identity, configuration, and meaning belong to the object, not to the
infrastructure that currently hosts it. Identity MUST be stable across move,
restore, and host crash. Code MUST NOT treat an infrastructure coordinate — an IP,
a port, a hostname, a filesystem path, a local integer, a venv location — as if it
were identity or logic. Such coordinates are injected from configuration; they
never appear hardcoded in component logic.
- **Kills:** Infrastructure Proxy (identity minted by, and trapped in, the host).
- **On this platform:** the hardcoded constants — `192.0.2.10:8001`,
  `~/src/5etools-kostadis/data`, `localhost:8000`, port `8077`, `~/.venvs/main` —
  are infrastructure proxies embedded in component logic. They move to
  `platform.yaml` and are injected; component code names *what it needs*
  ("the DGX endpoint"), never *where it is today*.

### III. Intrinsic State — no Horcruxes
State and metadata travel with the thing they describe; they do not live in a
separate side-database that must be hand-synced or separately migrated. Moving,
copying, or deleting an entity MUST NOT leave its metadata orphaned elsewhere.
Where state must be externalized, there MUST be a reconciliation protocol that
re-binds it — losing a derivable policy on a raw copy is acceptable; losing the
entity's own state is a failure.
- **Kills:** Fragmented State (dangling references, orphaned config, hand-synced truth).
- **On this platform:** there is **one** source of truth — `platform.yaml`. No
  per-tool constant is hand-maintained in parallel; the installer *renders* each
  component's native config from that single file, so the global truth is never
  forked across `config.yaml`, `mempalace.yaml`, `models.yaml`, and scattered env vars.

### IV. The Management Plane is a Transient Viewer
The thing that manages is an observer, not an owner. If the manager dies, the
managed objects survive unchanged; when it restarts it *reconciles* — it adopts
existing objects with their original identity and history (the Brick Test: wipe
the manager, point it at the objects, "Import"), it does not re-mint them as new.
A manager MUST be reconstructable from the objects it manages, never the reverse.
- **Kills:** Fragmented State / Split-Brain at recovery time.
- **On this platform:** `platform` installs, wires, and reports — it does not become
  a new thing the components depend on to function. Delete `platform` and the
  components still run from their own rendered configs. `platform install` on a
  fresh checkout reconstructs the wiring from `platform.yaml` + the component repos;
  nothing irreplaceable lives only in the manager.

### V. One Entity, One Database — No Split-Brain, No Stale Copies
A single entity has exactly one authoritative database — one source of write
authority for its state. An entity's truth MUST NOT be smeared across two stores
that are each updated independently and trusted to agree. If an update genuinely
must span multiple databases, the cross-database atomicity is an explicit,
designed part of the architecture — a distributed transaction, or an equivalent
named protocol (2PC, or a saga with compensating actions and a reconciliation
step) — never an implicit "write A, then write B, and hope."

The system MUST make it impossible to be forced into a merge conflict — at
restore *or* at runtime:
- **At restore:** because there is one authoritative store, there is exactly one
  thing to restore and nothing to merge. Two independently-owned stores restored
  from different points in time bring back a self-inconsistent entity; one store
  cannot. (This is the original "no split-brain after restore.")
- **At write, across interfaces:** every write path — CLI, API, UI — converges on
  the one authority. No interface keeps a private authoritative copy, so concurrent
  edits serialize against a single store and can never produce two conflicting
  truths to reconcile.
- **At read, against caches:** derived or cached copies are non-authoritative and
  MUST be kept coherent with the authority. A write is not *complete* until every
  derived copy is regenerated or invalidated, **or** every consumer validates its
  copy against the authority before acting and refuses to run on a mismatch (this
  is Principle I — a stale cache is a software ack the silicon has not confirmed).
  It MUST be impossible to change the authority through one path (e.g. the CLI) and
  leave another path running on a stale copy. A stale cache is a split-brain
  between the authority and the copy — the same disease at write time as at restore.
- **Kills:** Split-Brain — whether surfaced by restore (timestamp skew) or by a
  live write a cache missed.
- **The sin is multiple *authorities*, not multiple files.** What's forbidden is
  more than one independently-written / hand-maintained store of an entity's truth.
  A derived, read-only copy that is always regenerated from the one authority and
  kept coherent (the read-against-caches rule above) is not a second authority and
  is fine. Physical file count is irrelevant; *number of places you can edit and be
  believed* must be one.
- **Decision (2026-06-24):** the system as built today spreads state across multiple
  hand-maintained config files and databases. That is the bug this principle
  removes — not a compatibility surface to preserve. Breaking changes to components
  to reach one authority (collapsing a component-local database into `platform.yaml`,
  replacing a hand-edited config with a generated one) are explicitly accepted. See
  the V-over-VII precedence rule in Governance.
- **Pairs with Principle VI:** federate *across* entities; keep single-owner,
  atomic authority *within* an entity. Distribution is at the entity boundary,
  not inside it. Relates to III (state stays with its entity) and IV (the Brick
  Test — reconstruct cleanly after a wipe).
- **On this platform:** `platform.yaml` is the single authoritative store for the
  system's wiring/config entity. The installer *renders* each component's native
  config from it (derived, read-only copies) — it never creates a second authority
  that can drift. There is no parallel hand-maintained truth to fall out of sync.
  Restore is `platform install` re-run from the one `platform.yaml`; there is no
  second database to restore at a mismatched timestamp. If platform state ever must
  live in more than one store, the render/reconcile step is the explicit, designed
  transaction — documented as such, not assumed.
  - **The rendered configs are caches, so they fall under the coherence rule.**
    The trap to design out: edit `platform.yaml` (or any field) through one path and
    leave a component running on a stale render — your CLI-vs-cached-copy failure.
    The mitigations, in order of strength: (1) **one write path** — mutating
    `platform.yaml` is the *only* way to change config, and it always re-renders +
    signals affected components, so the write is not "done" until propagation
    completes (Principle I); (2) **freshness check** — each rendered file records a
    hash/version of the `platform.yaml` it came from, and a component refuses to run
    on a mismatch rather than silently using stale values (the "False Green
    Dashboard" caught, not hidden); (3) `platform status` flags any rendered config
    whose source hash no longer matches `platform.yaml` as a FAIL. A long-running
    process that cached config in memory at startup is the residual case — it must
    reload on the propagation signal or be restarted by the write path, never left
    silently stale.

### VI. Federated Authority, designed for input[∞]
Distributed reality is the default assumption: data is sharded, visibility is
partial, and success at the first input does not imply success at the
ten-thousandth. Designs MUST NOT assume global visibility or a single synchronous
local view. Avoid lethal centralization — a single counter, lock, or registry that
every operation must pass through. Prefer distributed authority with asynchronous
reconciliation over a central bottleneck that becomes the system's gravity well.
- **Kills:** Split-Brain (and the central-bottleneck failure it hides behind).
- **On this platform:** install and status operate per-component and degrade
  independently — one unreachable service yields one FAIL, not a wedged run.
  Dependency direction is explicit and acyclic; leaf libraries (e.g. `dgxlib`)
  never depend upward. No component is wedged waiting on a central platform daemon.

### VII. Reason in Logical Datasets, not their Backing Bytes
Model the domain entity and its invariants, not the strings, integers, arrays,
LUNs, or files that happen to back it today. Abstractions are chosen so that a
change of backing representation does not rewrite the logic above it. Thinking in
*state and entities* (the Architecturalist) beats thinking in *syntax and calls*
(the Script Scribe).
- **Kills:** Infrastructure Proxy at the abstraction layer.
- **On this platform:** components consume meanings — "the DGX endpoint", "the
  campaigns data root", "the rpg-lib service" — resolved from config. They do not
  hardcode the URL/path that is merely the current encoding of that meaning. The
  installer is the single place that knows the encoding.

### VIII. Transform the Constraint before Building Complexity (Lagrange)
When a problem is hard, first find the artificial constraint making it hard and
ask whether it can be removed, before building machinery to satisfy it. Many hard
problems are trivial in a shifted coordinate system. State plainly *what must be
true* for the design to work; if an assumed constraint isn't load-bearing, drop it
rather than engineer around it. Curiosity first, complexity last.
- **Kills:** accidental complexity (the OpEx tax of the economic lens below).
- **On this platform:** prefer *rendering each component's existing native config*
  over inventing a new shared runtime import every component must adopt — the lower
  coupling removes the hard problem instead of solving it. Reach for a new database,
  daemon, or shared library only after showing the simpler coordinate shift fails.

### IX. Observability — State and To-Do are Discoverable, not Remembered
The state of the system, and the work outstanding against it, MUST be discoverable
from the system itself — never held in an operator's memory. It is not enough to
answer honestly when asked (Principle I); the system MUST surface *what to ask*: what
has drifted, what is pending, what decision is owed. A correct-but-opaque system still
forces an expensive human back into the loop (cf. *Determinism is Trust*) — a truthful
answer is worthless to someone who doesn't know the question to ask. Prefer one honest
"what's true / what's next" view over state scattered across logs, branches, and tribal
knowledge.
- **Relation to I (distinct, not redundant):** Principle I governs the *honesty* of a
  report; IX governs its *completeness and discoverability*. A status can be perfectly
  truthful (I) yet opaque (violates IX) by omitting outstanding work it never thought to
  show. Honesty about what you display ≠ surfacing everything that needs attention.
- **Kills:** Opacity / Tribal State — state that is correct but only knowable by someone
  who already knows where to look.
- **On this platform:** `hypostasis status` + `mneme mp status` are the single honest
  state-and-to-do surface — render/version drift, stale indexes, undispositioned
  divergences, and **pending proposal branches awaiting integration** are all visible in
  one place. The proposal-aware status to-do (feature 002, GH #14) is the worked example:
  honest per-campaign state was not enough; the outstanding *merge* had to be surfaced,
  not remembered.

## Architecture is Destiny (why these principles are non-negotiable)

These are not stylistic preferences; they have economic force (the Value-Bridge lens):

- **Architecture is Destiny** — a bad architectural choice is a predictable future
  financial loss, not a cosmetic flaw. Review judges the choice, not just the code.
- **Complexity is Cost** — every extra database, manager node, daemon, or hand-synced
  config is a standing OpEx tax. Added moving parts must pay for themselves.
- **Determinism is Trust** — a system that is "maybe" cannot be automated; every
  non-deterministic seam forces an expensive human back into the loop. Determinism
  is the precondition for the reproducible install this project exists to deliver.

When a tradeoff is contested, translate it into these terms — reliability gap,
efficiency gap, agility/automation gap — and decide on the business cost, not taste.

## Authority & the Human Checkpoint

- **Human owns structure; the LLM renders within it.** Boundaries, dependency
  direction, identity/ownership decisions, and the config schema are *precision
  decisions* — the human author makes them. Spec Kit's generative steps
  (`/speckit.plan`, `/speckit.implement`) render inside that structure; they MUST NOT
  decide it. A first-pass LLM extraction is a draft to be reviewed, never an
  architectural ruling that feeds the next step unreviewed.
- This constitution and the spec bodies are authored by the human. Generated plans
  and tasks are reviewed against this constitution before they proceed.

## Governance

- This constitution supersedes other practices in `~/src/mneme`. Where a spec,
  plan, or generated task conflicts with a principle, the principle wins; the
  conflict is resolved or the deviation is explicitly justified in writing.
- **Precedence — V over VII when they conflict.** Principle VII's "render into each
  component's native config" is a means to *low coupling*, not a license to keep an
  independent authoritative store. When low-coupling convenience and single-authority
  (V) collide, single-authority wins: the component changes. The existing
  multi-config / multi-database layout is Fragmented State to be removed, not a
  constraint to honor — forcing a breaking change to eliminate fragmentation is
  sanctioned (decision 2026-06-24). Prefer eliminating a derived copy (component reads
  the one authority, or a coherently-regenerated render) over preserving a second
  hand-maintained store, even at the cost of coupling.
- **Every spec and plan review tests against Principles I–IX by name**, and against
  the five anti-patterns (Optimistic Lies, Infrastructure Proxy, Fragmented State,
  Split-Brain, Opacity / Tribal State). A design that trips one without written
  justification does not pass.
- The acid test for the first spec (`001-reproducible-install`) is a direct
  application of this constitution: one edited `platform.yaml` — the single
  authoritative store — brings the system up on a fresh venv with no manual path/IP
  edits (II, III, V); `platform status` reports observed installed versions +
  per-service health (I, VI); and `grep` proves the hardcoded constants moved out of
  logic into config (II, VII).
- **Amendments** require: a stated rationale, a version bump per the policy below,
  and a check that the dependent Spec Kit templates (`plan-template.md`,
  `spec-template.md`, `tasks-template.md`) and `CLAUDE.md` still agree with the
  changed principles.
- **Versioning:** semantic. MAJOR = a principle removed or redefined incompatibly;
  MINOR = a new principle or materially expanded guidance; PATCH = clarifications and
  wording that don't change meaning.

**Version**: 1.1.0 | **Ratified**: 2026-06-24 | **Last Amended**: 2026-06-26
