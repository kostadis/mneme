# Feature Specification: Manage Campaign Mempalaces

**Feature Branch**: `002-manage-campaign-mempalaces`

**Created**: 2026-06-25

**Status**: Draft

**Input**: User description: "a critical part of the system is that we store the documents of the adventure in per-campaign mempalaces. How the data is stored is captured in by a MEMPALACE_HOWTO.md in https://github.com/kostadis/campaigns, but each campaign does things slightly differently because they have evolved over time. there isn't a consistent approach and when we discover a new best practice, they don't all upgrade. What I want is mneme to update and manage all of the mempalaces but still allow for per campaign specific configuration. the per campaign specific configuration should be stored in the campaign not in mneme"

## Context & Problem

Each campaign keeps a semantic index ("mempalace") over its own adventure documents. How that index is shaped — which wings exist, which rooms/keywords route content, what is excluded, in what order content is indexed — is described in a prose recipe (`MEMPALACE_HOWTO.md`) that has evolved over time.

Today the campaigns are inconsistent by accident, not by design:

- One campaign is fully built out (multiple wings, an exclusions file, a usage guide).
- Another has only an exclusions file.
- Several have nothing at all.

When a better way to build a mempalace is discovered, it is applied to one campaign by hand and the others silently fall behind. There is no way to see, at a glance, which campaigns conform and which are stale, and no way to roll an improvement out to all of them without redoing the manual recipe per campaign.

The desired end state: **mneme manages and updates every campaign's mempalace**, while **each campaign's own choices stay stored in that campaign** — never copied into mneme. The shared, evolving *recipe* (the conventions everyone should follow) is one thing; each campaign's *choices made within that recipe* (its wings, rooms, keywords, exclusions) are another. Management must respect that split: propagate the shared improvements, preserve the per-campaign choices.

**mneme facilitates; the campaign decides.** What content a campaign indexes — its scope, what belongs in the index, what is excluded — is a per-campaign decision made by the human. mneme renders configuration, orchestrates indexing, and propagates shared conventions, but it never decides a campaign's scope.

**Writes are isolated from the GM's live work.** Per-campaign configuration lives in the campaigns version-control repository. mneme MUST NOT edit the active checkouts the GM is working in. Instead, mneme makes configuration changes in its own **private working copy** of the campaigns repository and propagates them through the repository (version control), so the GM adopts changes by pulling them — never by finding their working tree edited underneath them. Reads (status, conformance, index refresh) still observe the live active checkout, so reported state reflects reality.

**Adoption is gated on the campaign side.** There are two independent gates. First, mneme confirms (preview-then-apply) before it *publishes* a proposed change to version control. Second — and separately — each campaign has its own **manual adoption gate**: a human on the campaign side explicitly decides to adopt the new scheme and migrate to it. mneme never auto-merges a published change onto a campaign's canonical line. Adoption is per-campaign and opt-in; a campaign that has not yet adopted a published upgrade is a legitimate state, not a failure.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Refresh every campaign's mempalace from its own configuration (Priority: P1)

The Game Master maintains several campaigns. Adventure documents change constantly — new session chapters, re-run extractions, updated reference docs. With a single mneme command, the GM brings every campaign's index up to date using **each campaign's own stored configuration**: the right wings are mined in the right order, exclusions are honored, and no campaign is indexed using another campaign's settings.

**Why this priority**: This is the core "manage all the mempalaces" capability and the most frequent operation. It delivers value on its own even if nothing else ships — the GM stops hand-running per-wing mining across multiple campaigns.

**Independent Test**: Point mneme at the campaigns root and run a refresh. Verify each campaign's index reflects its current documents and its own wing/room configuration; a campaign with no configuration is reported as skipped (not failed); a campaign with broken configuration fails alone without stopping the others.

**Acceptance Scenarios**:

1. **Given** a campaigns root with several campaigns, each holding its own mempalace configuration, **When** the GM runs a refresh-all, **Then** every configured campaign's index is rebuilt from its own configuration, sub-scopes are indexed before the root so nothing is double-indexed, and a per-campaign result is reported.
2. **Given** a campaign whose documents changed since the last index, **When** the GM refreshes, **Then** that campaign's index reflects the changed documents.
3. **Given** a campaign with no mempalace configuration, **When** the GM refreshes all, **Then** that campaign is reported as "no configuration — skipped" and the run continues for the others.
4. **Given** a campaign with an invalid configuration, **When** the GM refreshes all, **Then** that one campaign fails with a clear reason and the other campaigns still refresh.

---

### User Story 2 - See the true state of every campaign's mempalace (Priority: P2)

The GM wants an honest, at-a-glance report of every campaign: is its index built, stale (documents changed since it was last indexed), missing, or out of step with the current recipe? The report reflects what is actually on disk, not what some record claims.

**Why this priority**: You cannot manage what you cannot see, and the divergence problem is invisible today. Status is the precondition for trusting any propagation step. It is P2 only because refresh delivers the headline value first.

**Independent Test**: Run a status command across the campaigns root and confirm each campaign is classified (built / stale / missing / divergent) based on inspection of the actual workspace, and that a campaign sharing a backing store with another is not conflated with it.

**Acceptance Scenarios**:

1. **Given** a set of campaigns in mixed states, **When** the GM runs status, **Then** each campaign is reported as built, stale, missing-config, or divergent-from-recipe, derived from observed state.
2. **Given** a campaign whose documents changed after its last index, **When** the GM runs status, **Then** it is reported as stale.
3. **Given** two campaigns that share one backing index store, **When** the GM runs status, **Then** each campaign's state is reported separately and not merged.

---

### User Story 3 - Propagate a newly discovered best practice to all campaigns (Priority: P2)

A better convention is discovered (for example: prefer a dedicated exclusions file over falling back to the version-control ignore file; standardize the indexing order; adopt a shared room-naming convention so searches can cross wings). With one operation the GM **publishes** that improvement as a proposal to **every** campaign at once. Each campaign's own content choices — its specific wings, rooms, and keywords — are preserved; only the shared convention changes. Publishing does not change any campaign's canonical configuration: each campaign is **adopted separately**, on the campaign side, when its owner is ready.

**Why this priority**: This directly removes the "they don't all upgrade" pain, but it depends on the manage/status foundation and on a clear split between shared recipe and per-campaign choice.

**Independent Test**: Introduce a recipe change, run propagation in preview, confirm every non-conforming campaign is listed with the exact change; publish, confirm the proposal exists in version control for each while no campaign's canonical configuration changed; adopt one campaign and confirm only that campaign now conforms, with its custom wings/rooms/keywords intact, while the others remain "upgrade available, not yet adopted."

**Acceptance Scenarios**:

1. **Given** a recipe improvement and several campaigns at different conformance levels, **When** the GM runs propagation in preview mode, **Then** mneme lists, per campaign, exactly what would change and what would be left untouched, and writes nothing.
2. **Given** the previewed changes, **When** the GM publishes them, **Then** mneme stages the change as a version-controlled proposal per campaign without altering any campaign's canonical configuration or any active checkout.
3. **Given** a published proposal, **When** a campaign's owner adopts it on the campaign side, **Then** that campaign follows the new convention while its content choices (wings, rooms, keywords, exclusions it deliberately set) are preserved, and other campaigns are unaffected.
4. **Given** a published proposal that a campaign has not adopted, **When** the GM runs status, **Then** that campaign is reported as "upgrade available, not yet adopted" — distinct from both "conformant" and "divergent by choice."
5. **Given** a campaign that deliberately diverges from the convention, **When** propagation would overwrite that deliberate choice, **Then** mneme surfaces the conflict instead of silently overwriting it.

---

### User Story 4 - Bootstrap a standard mempalace into a campaign that has none (Priority: P3)

A new or never-set-up campaign has no mempalace configuration. The GM bootstraps it: mneme writes a starter configuration — following the current recipe — **into that campaign**, ready for the GM to customize, after which it participates in refresh, status, and propagation like any other.

**Why this priority**: Useful onboarding, but the manage/status/propagate loop is more urgent for the campaigns that already exist.

**Independent Test**: Run bootstrap against a campaign with no configuration; verify standard configuration appears inside that campaign (not in mneme) and that a subsequent refresh builds its index.

**Acceptance Scenarios**:

1. **Given** a campaign with no mempalace configuration, **When** the GM bootstraps it, **Then** a starter configuration following the current recipe is written into that campaign.
2. **Given** a freshly bootstrapped campaign, **When** the GM refreshes all, **Then** that campaign's index is built like any other.

---

### User Story 5 - Adopt a new scheme and migrate a campaign to it, assistant-guided (Priority: P2)

When a campaign's owner is ready to take a published upgrade, they adopt it for that one campaign. Adoption may be more than swapping a configuration file: moving to a new scheme can require migrating existing data — re-shaping wings, splitting or relocating documents, re-indexing. The owner retrieves what mneme recommends for that campaign through **mneme's MCP server** (a tool that returns the target configuration mneme thinks the campaign needs) and, from the same server, **loads the management instructions on demand** to ground the work (and the campaign's own usage guide), then works out a **per-campaign migration plan interactively in a chat assistant**. The assistant drafts the plan in the campaign's context; the human reviews and approves it; execution follows the write-isolation and manual-adoption rules. Document content is preserved verbatim — migration may move or split files but never rewrites their text.

The assistant **reasons out the plan freely** rather than filling in a fixed template, because a mempalace's structure has to serve *this* campaign's needs — it is a judgment call, not a mechanical transform. mneme supplies the inputs (its recommendation, the campaign's current state) and enforces the invariants (verbatim content, write-isolation, post-migration verification); the **human-approval gate** is what makes free reasoning safe — nothing executes until the human approves.

**Why this priority**: It is the other half of propagation (US3) — publishing is inert until a campaign can actually adopt and migrate. It is per-campaign and interactive because the right structure depends on the campaign, so the plan is reasoned out case by case under human review, not generated automatically.

**Independent Test**: With a published proposal available, retrieve the target config for a campaign via the MCP tool; in an assistant session, produce a per-campaign migration plan; approve and execute it; confirm the campaign's index reflects the new scheme, document content is unchanged byte-for-byte, the active checkout was never edited by mneme, and the change reached the campaign only through the manual adoption step.

**Acceptance Scenarios**:

1. **Given** a published proposal, **When** the owner queries mneme's MCP server for a campaign, **Then** it returns the target configuration mneme recommends for that campaign, preserving the campaign's existing content choices where they do not conflict.
2. **Given** a target configuration, **When** the owner works through adoption in an assistant session, **Then** a per-campaign migration plan is produced for human review before any change is executed.
3. **Given** an approved migration plan that reorganizes documents, **When** it executes, **Then** files may be moved or split but their content is preserved verbatim, and the resulting index reflects the new scheme.
4. **Given** a completed migration, **When** mneme reports state, **Then** it confirms conformance by inspecting the actual migrated index, not by assuming the plan succeeded.
5. **Given** a migration plan that would rewrite or drop document content, **When** it is evaluated, **Then** the workflow refuses or flags it rather than silently losing content.

---

### Edge Cases

- **No configuration**: a campaign with no mempalace configuration is reported and skipped, never treated as a hard failure.
- **Invalid configuration**: a malformed per-campaign configuration fails that campaign in isolation; other campaigns proceed.
- **Stale index**: documents changed but the index was not refreshed → status must classify it as stale, not as healthy.
- **Indexing order**: when a campaign has sub-scopes that the root would otherwise re-index, sub-scopes are indexed first so content is not double-indexed.
- **Destructive setup steps**: a known recipe hazard where an initialization step overwrites the campaign's hand-tuned configuration must not destroy that configuration under management.
- **Shared backing store**: multiple campaigns may share one backing index store; their states must be reported and managed without conflation.
- **Conflict on upgrade**: a propagation step that would overwrite a deliberate per-campaign choice must surface the conflict rather than clobber it.
- **Manager loss (rebuild)**: wiping and reinstalling mneme must lose no per-campaign configuration and must not require re-entering it — management reconstructs from the campaigns themselves.
- **Live local edits**: the GM has uncommitted changes in an active checkout while mneme proposes a configuration change — mneme's write goes to its private working copy and the repository, so the GM's working tree is never disturbed and there is no surprise merge in their checkout.
- **Partial failure**: one campaign failing to build or check must not abort the run for the others.
- **Migration reorganizes documents**: files may be moved or split, but content is preserved verbatim; a plan that would rewrite or drop content is refused or flagged, never executed silently.
- **Interrupted migration**: a partial or interrupted migration must be safe to resume/re-run and must never leave a half-migrated index reported as healthy.
- **MCP server unavailable**: if mneme's MCP server is down, campaigns still run and the GM can still work; only the recommendation/adoption-planning convenience is unavailable (the manager is a transient viewer, not a runtime dependency).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: mneme MUST discover the set of campaigns to manage from configuration or observed workspaces (never a hardcoded list) and determine, per campaign, whether a mempalace configuration is present.
- **FR-002**: mneme MUST treat each campaign's mempalace configuration as authoritative and as living **within that campaign**. mneme MUST NOT store, cache as authority, or hand-maintain per-campaign configuration in its own configuration or state.
- **FR-003**: mneme MUST be able to (re)build/refresh each campaign's index using **only that campaign's own configuration** — its wing definitions, room/keyword routing, exclusions, and indexing order.
- **FR-004**: When refreshing, mneme MUST honor each campaign's exclusions and the required indexing order (sub-scopes before the enclosing scope) so that content is not double-indexed.
- **FR-005**: mneme MUST report observed mempalace state per campaign — derived from inspecting the actual workspace and index, never from a declared or cached value. Reported state MUST include: built, stale, missing-config, and, for any divergence from the recipe, the divergence together with its recorded **disposition** (see FR-027): **deliberate** ("decided this is right for this campaign"), **pending** ("not yet adopted / haven't gotten to it"), or **undispositioned** ("no reason recorded — needs a decision"). These three MUST be distinct; a deliberate, recorded divergence MUST NOT be reported as a problem, and an undispositioned divergence MUST NOT be reported as fine.
- **FR-006**: A campaign that lacks a mempalace configuration MUST be reported and skipped (not failed); a campaign whose configuration is invalid MUST fail in isolation without aborting the run for other campaigns.
- **FR-007**: mneme MUST maintain a single shared definition of the "current recipe" (the conventions every campaign should follow) against which conformance can be checked uniformly. The recipe covers two layers: (a) **mechanical/structural conventions** that apply to every campaign — exclusions style, indexing order, shared room-naming conventions, known setup hazards; and (b) a **recommended content scaffold** — e.g. the narrative/chronicle/<campaign> wing pattern — that mneme can offer or bootstrap but that a campaign MAY override or opt out of per-room. The mechanical layer is enforced as conformance; the scaffold layer is a recommendation, and a documented per-campaign deviation from it MUST NOT be reported as non-conformance.
- **FR-008**: mneme MUST be able to identify, for each campaign, how its configuration diverges from the current recipe, and report each divergence — together with its recorded disposition (FR-027) — without modifying anything.
- **FR-009**: mneme MUST be able to publish a recipe upgrade across all campaigns in one operation while **preserving each campaign's content-level choices** (its specific wings, rooms, keywords, and deliberate exclusions). An upgrade MUST NOT overwrite a deliberate per-campaign choice without surfacing the conflict.
- **FR-010**: Before propagating any change into a campaign (migration, upgrade, or bootstrap), mneme MUST present a preview of exactly what will change; the change MUST be a separate, explicit step — no silent mutation. The preview reflects the diff that will be made in the private working copy (FR-018).
- **FR-011**: mneme MUST be reconstructable from the campaigns alone: removing and reinstalling mneme MUST lose no per-campaign configuration and MUST NOT require re-entering it (adopt-by-reconciliation, not re-creation).
- **FR-012**: mneme MUST be able to bootstrap a standard mempalace configuration into a campaign that has none, writing it into that campaign for subsequent customization.
- **FR-013**: Where multiple campaigns share one backing index store, mneme MUST report and manage each campaign's state without conflating it with the others'.
- **FR-014**: mneme's cross-campaign operations MUST be safe to re-run: refreshing or conformance-checking an already-current campaign MUST not change it.
- **FR-015**: The machine-checkable definition of the current recipe MUST be **owned by mneme** (the manager's shared, versioned default applied across all campaigns). The prose `MEMPALACE_HOWTO.md` in the campaigns source remains the human-readable rationale; the mneme-owned recipe is its enforceable counterpart, not a copy maintained in the campaigns repo.
- **FR-016**: Each campaign MUST have a **single authoritative mempalace configuration file, stored in the campaign**, that mneme reads. The existing per-wing configuration files and the exclusions file MUST be treated as **derived artifacts rendered from that single authority** — never a second place to edit. Rendered artifacts MUST be kept coherent with the authority (regenerated on change), and mneme MUST be able to detect and flag a rendered artifact that no longer matches its source authority.
- **FR-017**: Adopting the single-authority configuration is a breaking change for campaigns whose configuration is currently spread across multiple per-wing files. mneme MUST provide a one-time migration that consolidates an existing campaign's scattered configuration into the single authoritative file, under the same preview-then-explicit-apply rule as any other change to a campaign (FR-010).
- **FR-018**: mneme MUST make all changes to a campaign's stored configuration in its own **private working copy** of the campaigns repository. mneme MUST NOT modify the active checkouts the GM works in. Changes MUST be propagated to campaigns through the repository (version control) — committed in the private working copy and pushed/proposed for the GM to adopt by pulling — never by editing a live working tree. **Exception:** the interactive confirmed-adopt path of FR-030 may write the active checkout, under the strict conditions stated there.
- **FR-019**: Read operations (status, conformance, refresh) MUST observe the live active checkout so that reported state reflects what actually exists on disk (Principle I); only *writes* are isolated to the private working copy.
- **FR-020**: mneme MUST facilitate but MUST NOT decide a campaign's scope: what content a campaign indexes, includes, or excludes is a per-campaign decision recorded in that campaign's authoritative configuration by the human. mneme renders, orchestrates, recommends, and propagates conventions, but a scope decision MUST originate from the campaign's configuration, never from mneme.
- **FR-021**: A published upgrade or migration MUST require a separate, manual, per-campaign **adoption** step on the campaign side before it changes that campaign's canonical configuration. mneme MUST NOT auto-adopt or auto-merge a published change onto a campaign's canonical line. Non-adoption MUST be a supported, non-failing state; campaigns adopt independently and at their own pace.
- **FR-022**: mneme MUST expose its recommendations through an **MCP server** — specifically, a tool that, given a campaign, returns the **target configuration** mneme believes that campaign should adopt (the published proposal resolved for that campaign, preserving its non-conflicting content choices), so an assistant or agent can retrieve it programmatically rather than the human hand-assembling it.
- **FR-028**: mneme's MCP server MUST serve, as **on-demand loadable capabilities** (not always-on context), the *instructions* for working with mempalaces — replacing the prior workflow of the human pasting docs into the assistant. Two kinds: (a) **management instructions** — how to build, configure, split, wing, and migrate a campaign mempalace (the procedural method historically captured in `MEMPALACE_HOWTO.md`); and (b) a **per-campaign usage guide** — how to search and use a specific campaign's palace (the content historically captured in that campaign's `MEMPALACE.md`). An assistant (or the human) MUST be able to pull either in only when needed.
- **FR-030**: mneme MAY adopt a recipe upgrade **directly into a campaign's active checkout** — but only through the interactive `adopt` tool/command, and only under all of: (a) a **single named campaign** (never a batch); (b) an explicit **two-step human confirmation** (preview → confirm) — a preview call writes nothing; (c) it writes **only mneme-managed files** (the `.mneme/mempalace.yaml` authority + the stamped derived wing files), **never** campaign content; (d) it leaves the change **uncommitted** for the human to review — it never auto-commits or pushes. All non-interactive paths (publish, batch adopt, bootstrap, migrate) remain working-copy-only (FR-018). *(Decision 2026-06-26: chat/agentic harnesses are where campaign work happens; this lets an assistant complete a per-campaign adoption in-conversation under explicit human confirmation, while the bounded blast radius — mneme-managed files only, uncommitted — keeps Principle V/IV intact.)*
- **FR-029**: The **management instructions** MUST be **mneme-owned and versioned with the recipe** (the prose method and the machine-checkable recipe are two faces of the one shared best practice, FR-015). The **per-campaign usage guide** MUST be **served from the campaign** (it is that campaign's intrinsic content — Principle III), never relocated into mneme. Serving instructions MUST remain read-only/advisory, so the server stays a transient viewer, not a runtime dependency (Principle IV).
- **FR-023**: Adopting a new scheme MAY require **migrating existing data** — re-shaping wings, splitting/relocating documents, re-indexing — not only replacing a configuration file. mneme MUST support a data migration as a distinct, per-campaign operation, separate from a no-migration configuration swap.
- **FR-024**: A migration plan MUST be **per-campaign** and MUST be produced under **human review in an interactive (assistant-assisted) workflow**. The assistant **reasons out the plan freely** — the mempalace structure must serve the specific campaign's needs, so mneme MUST NOT constrain the plan to a fixed template or deterministic transform; mneme supplies inputs (its recommendation, the campaign's current state) but does not dictate the resulting structure. The **human-approval gate is mandatory and load-bearing**: no migration plan may execute until the human approves it, and approval — not a deterministic generator — is the control point. Execution MUST still obey write-isolation (private working copy, never the active checkout — FR-018) and the manual adoption gate (FR-021), and the invariants FR-025 (verbatim content) and FR-026 (verify the actual result) MUST hold regardless of what the plan proposes.
- **FR-025**: Migration MUST preserve document content **verbatim**: it may move, split, rename, or re-index files, but MUST NOT rewrite or drop the content of a campaign's documents. A plan that would alter content MUST be refused or surfaced for explicit human decision, never executed silently.
- **FR-026**: After a migration, mneme MUST confirm the campaign conforms by inspecting the **actual resulting** index/configuration (Principle I), never by trusting that the plan ran to completion. If the result still diverges, mneme MUST surface the divergence and its disposition (FR-027) — distinguishing "the migration did not achieve conformance" (incomplete/failed) from "the human deliberately chose a structure that differs."
- **FR-027**: For every divergence from the recipe, mneme MUST record a per-campaign, per-divergence **disposition that explains why**, authored by the human and stored **in the campaign** (intrinsic state — never in mneme): **deliberate** (a decision that this is right for the campaign, carrying a short rationale) or **pending** (not yet adopted). mneme MUST NOT decide a disposition itself; it records, reads, and surfaces what the human declared. A divergence with no recorded disposition MUST be reported as **undispositioned — needs a decision** (adopt it, or record it as deliberate), and MUST NOT be silently treated as either conformant or as drift to be "fixed."

### Key Entities *(include if feature involves data)*

- **Campaign**: a self-contained adventure workspace under the campaigns root. Owns its documents and its mempalace configuration. The unit of management.
- **Per-campaign mempalace configuration (the authority)**: a single configuration file stored in the campaign holding the campaign's own choices — wings, room/keyword routing, exclusions, indexing order. The one place to edit a campaign's index settings; authoritative for that campaign; never owned by mneme.
- **Rendered per-wing artifacts**: the per-wing configuration files and exclusions file that the indexing layer consumes. Derived from the single per-campaign authority, kept coherent with it, and never edited directly.
- **Mempalace index**: the searchable semantic index built for a campaign from its documents according to its configuration. Derived data — rebuildable from documents + configuration.
- **Recipe (shared best practice)**: owned by mneme; two layers — enforced mechanical/structural conventions and a recommended (overridable) content scaffold. The shared part that evolves and is propagated, as distinct from per-campaign choices. `MEMPALACE_HOWTO.md` is its prose rationale.
- **Conformance report**: the per-campaign comparison of actual configuration/state against the current recipe, pairing each divergence with its recorded disposition (built / stale / missing / divergent-deliberate / divergent-pending / divergent-undispositioned).
- **Divergence disposition (the recorded "why")**: a per-campaign, per-divergence record — authored by the human, stored in the campaign — declaring *why* this campaign differs from the recipe: deliberate (with rationale) or pending. The thing that turns "non-conforming" into "non-conforming because ___." Read by mneme; never decided by mneme. Absent = undispositioned, which mneme flags as needing a decision.
- **Active checkout**: the campaign workspace the GM works in (where sessions are run and documents edited). Read by mneme; never written by mneme.
- **Private working copy**: mneme's own clone of the campaigns repository, where it stages configuration changes and from which it propagates them through version control. The only place mneme writes campaign configuration.
- **Target configuration (recommended)**: what mneme believes a campaign should adopt — the published proposal resolved for that campaign, preserving its non-conflicting choices. Served via mneme's MCP server; advisory until the campaign adopts it.
- **Migration plan**: a per-campaign, human-reviewed plan for moving a campaign from its current scheme to an adopted target, including any document reorganization and re-indexing. Drafted with assistant help, approved by the human, executed under write-isolation; never rewrites document content.
- **Management instructions**: the mneme-owned, versioned procedural method for building/configuring/migrating a mempalace (the `MEMPALACE_HOWTO.md` content as a served, loadable capability) — the prose counterpart to the recipe. Served on demand by the MCP server; grounds the assistant's free-form migration reasoning.
- **Campaign usage guide**: a campaign's own guide to using its palace (its `MEMPALACE.md` — wings, trust levels, search patterns, quirks). Stored in the campaign (intrinsic), served on demand by the MCP server when working in that campaign.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a single command, the GM obtains the true state (built / stale / missing / divergent) of **every** campaign without inspecting any campaign by hand.
- **SC-002**: A single command refreshes all configured campaigns' indexes from each campaign's own configuration; the GM no longer runs per-wing indexing per campaign by hand.
- **SC-003**: Publishing a newly discovered best practice to all campaigns is a single operation (replacing the per-campaign manual recipe edits done today); each campaign then reaches conformance with a single deliberate adopt action and no hand-editing of the recipe. Status always shows exactly which campaigns have adopted and which have an upgrade pending.
- **SC-004**: After a propagation, 100% of each campaign's deliberate content choices (wings, rooms, keywords) are preserved — zero unintended overwrites — and any genuine conflict is surfaced rather than silently applied.
- **SC-005**: No per-campaign configuration is stored in mneme: removing and reinstalling mneme, then pointing it back at the campaigns, reproduces the same management view with zero re-entry of per-campaign settings.
- **SC-006**: A campaign with missing or invalid configuration never aborts a cross-campaign run; the run completes for all other campaigns and reports the offender distinctly.
- **SC-007**: Every state mneme reports for a campaign matches what is actually on disk (an independent inspection of the campaign agrees with mneme's report in 100% of checked cases).
- **SC-008**: Each campaign's index settings are edited in exactly one place: changing the single per-campaign authority and refreshing leaves no rendered per-wing artifact out of sync, and mneme flags any rendered artifact whose source no longer matches.
- **SC-009**: No mneme operation ever modifies an active checkout: after any migrate/upgrade/bootstrap, an independent inspection of the GM's active checkout shows it unchanged by mneme, and all proposed changes are present in the repository for the GM to pull.
- **SC-010**: Migrations preserve document content verbatim: after any migration, every retained document's content is byte-for-byte unchanged; no migration rewrites campaign prose.
- **SC-011**: Adoption recommendations are retrievable programmatically: an assistant can obtain mneme's target configuration for a given campaign through the MCP server without the human hand-assembling it.
- **SC-012**: Every reported divergence carries a recorded reason or is explicitly flagged as undispositioned: for 100% of non-conforming campaigns, status shows either "deliberate (with rationale)," "pending," or "needs a decision" — mneme never reports a campaign as simply wrong without surfacing the recorded why or the absence of one. The recorded reason survives wiping and reinstalling mneme (it lives in the campaign).
- **SC-013**: An assistant can carry out a management or migration task by loading the method and the campaign's usage guide **from the MCP server on demand**, with the human pasting **zero** instruction documents — replacing the prior copy-paste-the-HOWTO workflow.

## Assumptions

- The campaigns root (the active checkouts) is already known to mneme through its existing environment configuration (the same mechanism that resolves where campaigns live for the existing lifecycle commands); this feature reuses it for reads rather than introducing a new source of truth.
- Per-campaign configuration is stored in a version-controlled campaigns repository (`github.com/kostadis/campaigns`); mneme can obtain and maintain its own private working copy of that repository for writes.
- Propagation publishes a change as a version-controlled proposal that a campaign adopts by a manual, per-campaign action (FR-021); the precise mechanism that carries the proposal (e.g. a dedicated branch the campaign merges, or a pull request the campaign approves) is a planning detail — either satisfies the requirement that mneme never alters a campaign's canonical line or active checkout without that manual adoption step.
- Writing campaign configuration (migrate/upgrade/bootstrap) follows a preview-then-explicit-apply model consistent with the project's existing dry-run/apply conventions; nothing is propagated without an explicit step.
- The underlying single-campaign index build/refresh/search capability already exists; this feature orchestrates and standardizes it across many campaigns rather than reimplementing indexing.
- "Stale" is determined by comparing the campaign's source documents against the existing index (e.g., documents changed since the index was last built); the exact freshness signal reuses whatever the indexing layer already exposes.
- Authoring of adventure document *content* (the prose itself) is out of scope and is never rewritten by this feature; migration may, however, reorganize document files (move/split/rename) and rebuild the derived index, always preserving content verbatim.
- mneme's MCP server is an advisory/query surface for retrieving recommendations, **serving loadable instructions**, and driving adoption interactively; campaigns do not depend on it to run, and if it is unavailable the GM can still work (the manager is a transient viewer — Principles IV and VI).
- The procedural `MEMPALACE_HOWTO.md` content becomes the mneme-owned management instructions (served on demand); a copy may remain in the campaigns source as rationale, but mneme owns the served, versioned method. Each campaign's `MEMPALACE.md` stays in the campaign and is served per-campaign — it is not relocated into mneme.
- The interactive adoption/migration workflow runs in a chat assistant with mneme's MCP server connected (e.g. this CLI). The assistant reasons out the migration plan freely — a mempalace's structure has to serve the specific campaign's needs, so it is a judgment call rather than a templated transform. This deliberately differs from the general "LLM renders, never structures" default; it is made safe by the project's human-checkpoint rule applied at the approval gate (the human approves before anything executes) plus the hard invariants of verbatim content (FR-025), write-isolation (FR-018), and post-migration verification (FR-026). mneme does not constrain the plan's structure; the human owns the go/no-go.
- The prose `MEMPALACE_HOWTO.md` remains the human-readable rationale; the machine-checkable recipe this feature introduces is owned by mneme and is the enforceable counterpart to it, not a replacement for the prose.
- Consolidating each existing campaign's scattered per-wing configuration into a single authoritative file is an accepted one-time breaking change (consistent with the constitution's single-authority decision of 2026-06-24), performed via the migration in FR-017 under preview-then-apply.
