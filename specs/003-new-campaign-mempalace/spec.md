# Feature Specification: Mempalace Bring-Up for a New Campaign

**Feature Branch**: `003-new-campaign-mempalace`

**Created**: 2026-06-26

**Status**: Draft

**Input**: User description: "mempalace bring up for a new campaign - see issues in github" (GitHub #4 — configure the per-campaign mempalace, incl. the migrated 0006 "campaign creation must produce a mneme-usable mempalace"; GitHub #12 — provision + back up the per-campaign mempalace data store)

## Context & Problem

Feature 002 gave `mneme` the ability to **manage** an *existing* campaign's mempalace: a single authority in the campaign, stamped derived config, honest status, refresh, publish/adopt/migrate. But it assumes the campaign already has a mempalace set up. A **brand-new campaign** — one that has documents but has never been through bring-up — is born with nothing: no authority, no provisioned index store, no built index, no backup. `mneme mp status` reports it `missing_config` and it falls silently outside management — the "inconsistent by accident" problem 002 exists to kill, reintroduced at creation time (GitHub #4 / 0006).

There are two planes to stand up, and today nothing owns the end-to-end:

- **Config plane** (mneme's job, #4 / 0006): a per-campaign authority `.mneme/mempalace.yaml` chosen from the recipe scaffold, with the derived wing config rendered and stamped — so the campaign is conformant and manageable from birth.
- **Data plane** (hypostasis's job, #12): the index **store** provisioned for the campaign, the **first mine** run to build the index, and — because that index is expensive to regenerate — **backup** so the work is protected.

This feature is the **bring-up**: one operation that takes a new campaign from "just has documents" to "configured, provisioned, indexed, observable, and protected" — correctly sequenced, idempotent, and honest about what it did and what (if anything) is still owed.

### Ground truth (see [research-current-state.md](./research-current-state.md))

A forensic pass over the real system corrected three premises this spec was first drafted on:

- **Per-campaign stores already exist.** Each campaign already has its own store at
  `~/.mempalace/palaces/<campaign>/`; the "campaigns share one store" idea was stale. So bring-up is
  not about *establishing* isolation — it is about **formalizing and de-fragmenting** a per-campaign
  setup that today is wired by hand and **inconsistently** (some campaigns are missing their store
  pointer and silently resolve to the wrong store; one has no config at all).
- **The store is turbovecdb, not chroma.** The store's source of truth is `store.sqlite3` (the
  bindings/embeddings); the ANN index alongside it is a rebuildable cache. (Stray `chroma.sqlite3`
  files are dead migration legacy.)
- **A campaign's mempalace wiring is fragmented across three places** (Principle V violation): the
  campaign's `mempalace.yaml` (its store pointer + wings), a section in the campaign's `config.yaml`,
  and a **global registry outside the campaign**. Bring-up should render all of these from the one
  in-campaign authority, so the campaign owns its own wiring.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Stand up a new campaign's mempalace end-to-end (Priority: P1)

A Game Master has a new campaign with documents but no mempalace. With one bring-up operation, the campaign goes from nothing to a working, searchable index: a starter configuration is written into the campaign (chosen to fit what the campaign actually has), the index store is provisioned, and the documents are indexed for the first time — in the correct order, with no manual per-step recipe-following.

**Why this priority**: This is the core value and the MVP — it turns "a folder of documents" into a managed, searchable campaign memory in one step, closing the creation-time gap that 002 left open.

**Independent Test**: Point bring-up at a new campaign that has documents but no `.mneme/` config; afterward the campaign has a conformant configuration, a built index over its documents, and is searchable — with the whole thing reported as done.

**Acceptance Scenarios**:

1. **Given** a new campaign with documents and no mempalace configuration, **When** the GM runs bring-up, **Then** a starter authority is written into the campaign (fitting its layout), the store is provisioned, and the documents are indexed — sequenced correctly (configure → provision → index).
2. **Given** a successful bring-up, **When** the GM searches the campaign, **Then** results come back over the campaign's own documents.
3. **Given** a new campaign with no prior mempalace setup, **When** bring-up runs, **Then** it produces the single authority + rendered config faces from scratch (a campaign that already carries ad-hoc config is out of scope — handled once by the migration, GH #24).

---

### User Story 2 - The new campaign is immediately observable and conformant (Priority: P2)

The moment bring-up completes, the new campaign appears in the system's status as built and conformant — never `missing_config`, never silently outside management. The bring-up itself reports what it did and surfaces anything still owed (e.g., a configuration choice the GM should review).

**Why this priority**: Per the constitution's Observability principle, a campaign that exists but isn't visible in the to-do/state surface is exactly the opacity we forbid. Bring-up must make the campaign discoverable, not leave the GM to remember it was set up.

**Independent Test**: Run bring-up, then run status across campaigns; the new campaign shows as built/conformant with its recipe version recorded, and any deviation it carries is surfaced with a reason or flagged as needing a decision.

**Acceptance Scenarios**:

1. **Given** a freshly brought-up campaign, **When** the GM runs status, **Then** it is reported built and conformant on the current recipe — not `missing_config`.
2. **Given** bring-up finishes, **When** it returns, **Then** it reports each step's observed outcome (configured / provisioned / indexed) and any owed follow-up, rather than a bare "done".

---

### User Story 3 - Preserve the bindings with a backup, restorable without re-embedding (Priority: P2)

Computing the embeddings (the **bindings**) is the expensive part of building the index — it runs the whole campaign through the embedding service. Bring-up protects that work with a backup of the bindings, and a later restore brings them back **as-is** — it does **not** re-embed. If sources changed since the backup, the store reconciles itself (it prunes entries whose source is gone), so the restore is safe without a full rebuild. Re-embedding from scratch is a deliberate, explicit operation the GM invokes only when needed (e.g., changing the embedding model).

**Why this priority**: The bindings are an expensive asset, not throwaway. Losing them means re-running every embedding; restoring them is cheap and is the normal recovery path. The index remains *derivable* in principle, but the operational policy is preserve-and-restore, never silent recompute. Correctness is kept by the store's own auto-reconciliation (no stale entries served), not by a rebuild gate.

**Independent Test**: Bring up a campaign, back up its bindings; remove/damage the store; restore; confirm the bindings come back **without re-embedding**, and that entries whose source has since been deleted are pruned automatically (not silently served). Confirm a from-scratch re-embed only happens when explicitly requested.

**Acceptance Scenarios**:

1. **Given** a brought-up campaign, **When** bring-up completes, **Then** a backup of the **bindings** exists (the source-of-truth store), clearly marked derived/disposable, excluding the rebuildable index cache and any dead legacy store files.
2. **Given** a damaged/removed store and a backup, **When** the GM restores, **Then** the bindings are recovered **without re-embedding**, and any entries whose source is now gone are reconciled away automatically.
3. **Given** the GM explicitly requests a from-scratch re-generation, **When** it runs, **Then** the bindings are recomputed — and this is the **only** path that re-embeds.

---

### User Story 4 - Re-running bring-up is safe; starting a campaign verifies it's brought up (Priority: P3)

Running bring-up again on an already-set-up campaign verifies and repairs rather than duplicating or clobbering. And when the GM starts working on a campaign, the system confirms its mempalace is actually brought up and healthy before proceeding — it won't quietly run against a half-set-up campaign.

**Why this priority**: Idempotence makes bring-up safe to re-run after partial failures; the start-time check keeps a not-brought-up campaign from being used as if it were ready (honest gating).

**Independent Test**: Run bring-up twice and confirm the second run changes nothing it shouldn't; start a campaign whose index is missing and confirm the system flags it rather than proceeding silently.

**Acceptance Scenarios**:

1. **Given** an already-brought-up, healthy campaign, **When** bring-up runs again, **Then** it is a no-op (or a reported repair), never a duplicate or a clobber.
2. **Given** a campaign that was never brought up (or whose index is missing), **When** the GM runs `mneme up`, **Then** `mneme up` **fails** (refuses to start the runtime) and reports the mempalace as not-ready — it does not silently proceed and does not bring the mempalace up itself.

---

### User Story 5 - Search resolves to the right store everywhere — CLI-by-directory and the campaign's MCP (Priority: P2)

Whether the GM searches from the **command line inside the campaign's directory**, or through the **campaign's own search assistant (MCP)**, the query hits **that campaign's** store — never a default or another campaign's. Bring-up wires both from the one authority.

**Why this priority**: Searching the wrong store is a silent correctness failure — a campaign with a missing or stale pointer quietly answers from the wrong store (this is a real, observed bug today: two campaigns silently resolve to a default store). Both search paths must be pinned to the campaign's store at bring-up, or the whole feature gives confidently-wrong answers.

**Independent Test**: From inside each campaign's directory the CLI resolves to that campaign's store; the campaign's MCP search targets the same store; a campaign with a missing/garbled pointer is fixed at bring-up, not left silently resolving elsewhere.

**Acceptance Scenarios**:

1. **Given** a brought-up campaign, **When** the GM runs the mempalace CLI from inside the campaign directory, **Then** it resolves to that campaign's store (not a default or another campaign's).
2. **Given** a brought-up campaign, **When** the GM searches via the campaign's MCP, **Then** results come from that campaign's store.
3. **Given** a campaign whose store pointer is missing or points elsewhere, **When** bring-up runs, **Then** it renders the correct pointer + MCP registration and the wrong-store resolution is fixed — not left silent.

---

### Edge Cases

- **No documents yet**: a campaign with configuration but no indexable documents → bring-up sets up config + provisions the store, reports "nothing to index yet," and is not a failure.
- **Pre-existing ad-hoc config**: a campaign that already carries hand-made/fragmented mempalace config is **out of scope** for bring-up — it is handled once by the migration (GH #24), not reconciled here.
- **Shared global registry**: stores are dedicated per campaign; the only shared artifact is `~/.mempalace/config.json` — rendering MUST merge this campaign's entry, never clobber another's (the rest of a campaign's wiring is its own files).
- **First mine fails partway**: bring-up leaves a clearly *not-done* state (reported as incomplete), never a half-built index passed off as ready.
- **Store provisioning fails / backup location unavailable**: the failing step is isolated and reported; bring-up does not claim success.
- **Re-run after partial failure**: bring-up resumes/repairs idempotently to a complete state.
- **Backup taken, documents then change**: a later restore preserves the bindings and the store auto-prunes entries whose source is gone — no full rebuild, no stale content served.
- **Bringing up one campaign**: must not require or disturb other campaigns (federated; one failure is isolated).
- **Missing/garbled store pointer**: a campaign whose pointer is absent or points elsewhere MUST NOT silently resolve to a default/other store — bring-up renders the correct pointer (CLI-by-directory and the MCP follow it), and status flags any campaign still resolving wrong.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a single **bring-up** operation that takes a new campaign from "documents, no mempalace" to configured + provisioned + indexed, performing the steps in a correct, declared order (configure → provision → first index).
- **FR-002**: Bring-up MUST write a starter per-campaign **configuration** (the single authority that lives in the campaign) chosen to fit the campaign's actual layout, and record the current recipe version so the campaign starts **conformant** (never `missing_config`) — reusing the feature-002 bootstrap/consolidation behavior. The authority MUST also carry the campaign's **store pointer** (which dedicated store this campaign uses) so the campaign's wiring is self-contained.
- **FR-002a**: Bring-up MUST **render all of the campaign's mempalace wiring from that one authority** — the store-pointer/wing config the indexer reads (so directory-context CLI resolves right, FR-016), the search-side config the runtime reads, the per-campaign search-interface (MCP) registration (FR-017), and any entry in a global registry — so the same truth is never hand-maintained in multiple places (de-fragmentation). A campaign's wiring MUST NOT silently resolve to a different campaign's store.
- **FR-003**: Bring-up assumes a campaign with **no prior mempalace setup** (greenfield). Bringing the *existing* ad-hoc fleet — campaigns that already carry partial / hand-made / fragmented config — onto the scheme is the **one-time migration's** job (GH #24), **not** this feature. 003 carries no brownfield-reconciliation logic.
- **FR-004**: Bring-up MUST **provision the index store** for the campaign and run the **first index** over the campaign's documents, in the campaign's own configured order.
- **FR-005**: Bring-up at **creation time** MAY write directly into the new campaign's workspace (it is being created); this is the explicit exception to the management-time rule that writes go through a private working copy — a *later* re-configuration/migration still goes through the working copy. The two paths MUST stay distinct.
- **FR-006**: After bring-up, the campaign MUST be **immediately observable** in status as built/conformant, with its recipe version recorded; bring-up MUST **report each step's observed outcome** and any owed follow-up (Observability — never a bare success, never silently outside management).
- **FR-007**: Bring-up MUST treat the index as **derived, non-authoritative** data: the authoritative inputs are the documents + configuration (already version-controlled). The index is rebuildable and MUST NOT be treated as a source of truth.
- **FR-008**: Bring-up MUST be **idempotent**: re-running on an already-set-up, healthy campaign changes nothing it shouldn't (a no-op or a reported repair), and a partial/interrupted bring-up MUST be safe to resume to a complete state and MUST NOT be reported as ready while incomplete.
- **FR-009**: Bring-up of one campaign MUST be **isolated**: it MUST NOT require or disturb other campaigns. Stores are dedicated per campaign (FR-013), so the only shared artifact is the global registry (`~/.mempalace/config.json`) — rendering it MUST **merge** this campaign's entry and never clobber another's.
- **FR-010**: `mneme up` brings up the campaign **runtime/environment**, not the mempalace. It MUST **health-gate** the campaign's mempalace and **fail** (refuse to start the runtime) if the mempalace is not brought up or not healthy — mirroring how it already gates on the substrate. It MUST NOT itself perform bring-up.
- **FR-011**: Bring-up MUST **back up the bindings** — the expensive computed embeddings that constitute the index's source of truth — and mark the backup clearly as derived/disposable (not an authority). The backup MUST exclude rebuildable artifacts (the ANN index cache, which regenerates from the bindings without recomputing embeddings) and any dead legacy store files.
- **FR-012**: A **restore** MUST **preserve the bindings as-is by default** — it MUST NOT re-generate (re-embed) from scratch. The system relies on the store's **own automatic reconciliation** (it prunes entries whose source is gone) so a restored store self-corrects rather than serving stale content; new content is added incrementally by a normal index run, not a full rebuild. **Full re-generation (re-embed from scratch) MUST be a separate, explicit, opt-in operation** (e.g., an embedding-model change) — never the automatic behavior. The system MUST surface, after a restore, that bindings were preserved (and any reconciliation that pruned entries).
- **FR-013**: Each campaign MUST have its **own dedicated store** (this is already the system's model), so it can be provisioned, backed up, restored, and deleted **independently of every other campaign**. Bring-up MUST make a new campaign's dedicated store and its **store pointer** consistent — a campaign MUST NOT be left without a pointer (which would silently resolve to a shared/default store). Migrating the *existing* ad-hoc fleet onto this scheme is the separate one-time migration (GH #24), out of scope here; 003 is specced greenfield.
- **FR-015**: The campaign's **in-campaign authority is the single source of the store pointer** (Principle V/III — the campaign owns its own wiring). Every other place that names the store — the global `campaign→store` registry, the search-side config, and the per-campaign search-interface (MCP) registration — MUST be **rendered from that authority** and kept coherent (derived copies, never a second hand-maintained truth). (Decided 2026-06-26.)
- **FR-016**: From **within a campaign's directory**, the mempalace command line MUST resolve to **that campaign's store** (directory-context resolution via the rendered store pointer). Bring-up MUST make this true — running the indexer/search from inside the campaign "just works" on the right store, and a campaign MUST NOT be left in a state where the command line silently resolves to a default or another campaign's store.
- **FR-017**: Bring-up MUST register a **per-campaign mempalace search interface (MCP)** pointed at that campaign's store, rendered from the same authority, so search performed while working in the campaign targets the right store. The registration MUST stay coherent with the authority (re-rendered if the store pointer changes), and MUST NOT hardcode a path that bypasses the campaign's pointer.
- **FR-014**: Bring-up MUST be a distinct, **explicit one-time operation** (configure → provision → first index → backup). `mneme up` MUST NOT perform bring-up; it only health-gates and fails per FR-010. Re-running bring-up is a verify/repair (FR-008), not a re-set-up on every start.

### Key Entities *(include if data involved)*

- **New campaign**: a campaign workspace with documents but no (or partial) mempalace set up — the input to bring-up.
- **Per-campaign configuration (authority)**: the single in-campaign source of truth for the campaign's index (wings/rooms/exclusions/order + recipe version), written/consolidated at bring-up. (Same entity as feature 002.)
- **Index store**: the provisioned backing store that holds the campaign's built index. Derived; rebuildable; protected by backup; never an authority.
- **First index**: the index built over the campaign's documents during bring-up.
- **Bindings backup**: a derived, disposable copy of the **bindings** (the turbovec `store.sqlite3` source-of-truth), **excluding** the rebuildable index cache and dead legacy. Restorable **as-is** (no freshness gate) — correctness comes from the store's auto-reconciliation (it prunes entries whose source is gone), not from a rebuild. Re-embedding from scratch is a separate explicit operation.
- **Bring-up report**: the per-step observed outcome (configured / provisioned / indexed / backed-up) plus any owed follow-up — the observability surface for the operation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A GM can take a new campaign from "documents only" to "searchable, managed mempalace" in a **single** bring-up operation, with **zero** manual per-step recipe-following.
- **SC-002**: After bring-up, the campaign is **100% observable** — it appears in status as built/conformant on the current recipe, never `missing_config`.
- **SC-003**: Bring-up is **idempotent** — a second run on a healthy campaign produces no unintended change; an interrupted bring-up is never reported ready while incomplete.
- **SC-004**: Bindings can be **recovered from backup without re-embedding** in 100% of restores; entries whose source has been deleted are reconciled away rather than served; a from-scratch re-embed happens **only** when explicitly requested.
- **SC-005**: Bringing up or backing up one campaign **never** disturbs another (verified: other campaigns' state and data are unchanged by a single-campaign bring-up).
- **SC-006**: Starting a not-brought-up campaign is **caught** (reported not-ready), not run as if ready, in 100% of checked cases.
- **SC-007**: The index is verifiably **non-authoritative**: deleting the index store and re-running bring-up reproduces an equivalent index from the documents + configuration alone (the authoritative inputs survive in version control).
- **SC-008**: After bring-up, search targets the right store from **every** path — from each campaign's directory the command line resolves to that campaign's store, and the campaign's MCP search targets the same store — with **zero** wrong-store resolutions across all campaigns (the missing-pointer silent-wrong-store failure cannot occur).

## Assumptions

- A "new campaign" already exists as a workspace with its documents (created by hand or by an upstream tool); there is no separate "create the campaign" command in scope — bring-up operates on an existing-but-unset-up campaign directory.
- Bring-up reuses feature 002's building blocks: the recipe + scaffold, the single-authority bootstrap/consolidation, rendering, mining orchestration, and honest status. This feature adds the **store provisioning, first-mine sequencing, backup/restore, creation-time write path, and the start-time readiness gate**.
- The indexing capability itself (turning documents into a searchable index) already exists and is invoked, not reimplemented.
- Backup storage is a location distinct from the campaigns version-control repository (backups are large derived blobs, not authoritative content).
- Per-campaign dedicated stores are **already the system's model** (verified: `~/.mempalace/palaces/<campaign>/`); this feature does not invent them, it makes their wiring consistent and self-contained. The store is **turbovecdb**: the source of truth is the bindings store (`store.sqlite3`); the ANN index alongside is a rebuildable cache; stray `chroma.sqlite3` files are dead migration legacy and are out of scope except to be ignored/cleaned. (See [research-current-state.md](./research-current-state.md).)
- Real campaigns live under the configured campaigns root (today `~/campaigns/`), not the scratch tree. Embeddings/LLM are served by local substrate endpoints that must be reachable for an index run; a new campaign's bring-up depends on that substrate being up (relates to substrate bring-up, GH #1).
- `mneme up` is the campaign **runtime** bring-up; it gates on (and fails for) an un-brought-up mempalace but never performs mempalace bring-up itself (decided 2026-06-26) — keeping the heavy one-time set-up out of the per-start path.
- **Greenfield scope (decided 2026-06-26).** This feature brings up a campaign with **no prior mempalace setup**. The existing ad-hoc fleet is brought onto the scheme by a **separate one-time migration** (full rebuild allowed; sequenced after hypostasis — GH #24). Per that decision, **no requirement or implementation consideration in 003 carries brownfield-migration logic** — keeping the feature greenfield, deterministic, and clean (Complexity is Cost).
- The constitution (v1.1.0) governs: single authority in the campaign (V), index-as-derived-cache with re-index as ground truth (V/IV), honest observed status + a discoverable to-do (I/IX), and per-campaign federation (VI).
