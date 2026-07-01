# Feature Specification: Multi-Root Campaign Discovery & Membership

**Feature Branch**: `005-multi-root-campaigns`

**Created**: 2026-06-27

**Status**: Draft

**Input**: User description: "Multi-root campaign discovery: the managed campaigns location becomes one parent directory holding one or more independent trees (possibly from different remotes and/or sparse checkouts); mneme discovers campaigns across all trees, observes git rather than driving it, keeps single-location config working, and refuses to silently resolve a campaign name that is ambiguous across trees. Each campaign self-declares which mneme owns it via a `.mneme/owner.yaml` record. A new `mneme integrate` command claims a campaign (drops the owner record) as a stage before full bring-up. The owner is a logical, host-independent identity so a campaign can, in the long run, be brought up by a hypostasis running on a different physical machine. Unblocks the toee split-brain."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Discover campaigns across several trees (Priority: P1)

The operator keeps campaigns in more than one place: a monorepo tree holding most
campaigns, plus one or more standalone trees that each came from a different remote
(and may be sparse checkouts). The operator declares the set of trees mneme should
manage, and every mneme operation that works over "all campaigns" — status, refresh,
render — sees campaigns from **all** declared trees as one fleet.

**Why this priority**: This is the core capability and the reason for the feature.
Without it the operator is forced into a single tree, which is the constraint this
feature removes. It is the MVP: once campaigns from multiple trees are discoverable,
the rest is safety, ownership, and compatibility around it.

**Independent Test**: Declare two trees (a monorepo tree with several campaigns and a
standalone single-campaign tree). Run the fleet-wide status. Verify every campaign
from both trees appears, each with its correct path, authority presence, and minable
wings — and that nothing from outside the declared trees appears.

**Acceptance Scenarios**:

1. **Given** two trees are declared and each contains campaigns, **When** the operator
   runs the fleet-wide status, **Then** campaigns from both trees are listed in one
   stable, deterministic ordering.
2. **Given** a standalone tree whose single campaign lives one level below the tree
   root (e.g. `<tree>/toee`), **When** discovery runs, **Then** that campaign is found
   using the same immediate-subdirectory rule applied to every tree.
3. **Given** a declared tree that contains no campaigns, **When** discovery runs,
   **Then** it contributes nothing and does not cause the run to fail.

---

### User Story 2 - Existing single-location setups keep working (Priority: P2)

An operator who has only ever pointed mneme at one location must see no change in
behavior. Their existing configuration continues to load and discover campaigns
exactly as before, with no edits required.

**Why this priority**: Backward compatibility protects every already-working campaign
from a config-shape change. It is not the headline capability, but shipping the
headline without it would be a regression for the current setup.

**Independent Test**: Take a configuration that declares a single location (the
pre-feature shape). Run discovery and status. Verify results are identical to the
pre-feature behavior — same campaigns, same paths, same outcomes.

**Acceptance Scenarios**:

1. **Given** a configuration that names exactly one campaigns location in the old
   single-value shape, **When** mneme loads it, **Then** it is accepted without error
   and treated as a single-tree fleet.
2. **Given** that single-location configuration, **When** discovery and status run,
   **Then** the output matches the pre-feature behavior with no observable difference.

---

### User Story 3 - Never silently resolve an ambiguous campaign (Priority: P2)

When the operator names a single campaign to act on (status, render, backup, bring-up,
etc.), and that name exists under more than one declared tree among the campaigns this
mneme owns, mneme must refuse and say so — naming the conflicting trees — rather than
silently picking one. This is the safety property that makes a multi-tree fleet
trustworthy.

**Why this priority**: A silent wrong-tree pick is a Split-Brain / Optimistic-Lie
failure: the operator believes they acted on one campaign while mneme acted on another.
Surfacing it (Observability) lets the operator resolve the duplication on purpose
instead of discovering it later as corruption.

**Independent Test**: Place a campaign of the same name, both owned by this mneme, under
two declared trees. Run a name-based command. Verify it fails with an error that names
both trees and the ambiguous campaign, and that no side effect occurred.

**Acceptance Scenarios**:

1. **Given** the same campaign name exists under two declared trees and both are owned
   by this mneme, **When** the operator runs a name-based command, **Then** the command
   fails before any side effect with an error identifying the campaign and every tree it
   was found in.
2. **Given** a campaign name that exists under exactly one declared tree, **When** the
   operator runs a name-based command, **Then** it resolves to that one campaign and
   proceeds normally.
3. **Given** a campaign name that exists under no declared tree, **When** the operator
   runs a name-based command, **Then** it fails with a clear not-found error that lists
   the trees that were searched.
4. **Given** a same-named campaign where one copy is foreign-owned (US4), **When** a
   name-based command runs, **Then** the foreign copy is excluded from resolution and
   surfaced separately, not counted as ambiguity.

---

### User Story 4 - Claim a campaign (`mneme integrate`) and self-declared ownership (Priority: P2)

A campaign is discovered read-only; nothing is written to it until the operator
explicitly claims it. The operator runs **`mneme integrate <campaign>`**, which drops a
small `.mneme/owner.yaml` naming the owning mneme — a lightweight claim that marks the
campaign as belonging to this mneme *without* doing the full bring-up (many campaigns
need a lot of configuration before they are ready to provision). Full `mneme up`
provisions an owned campaign (and integrates it first if it was not already claimed).
Fleet boot/sync never claims on its own — it only *reports* campaigns that are
discovered-but-un-integrated. A campaign already claimed by a *different* mneme is never
managed or re-stamped; it is surfaced as foreign-owned for an explicit decision.
Ownership is reconstructable from the campaigns alone: a runtime carrying this mneme's
identity, pointed at the trees, re-adopts exactly its own campaigns from their
`owner.yaml` records, with no central registry (the Brick Test).

**Why this priority**: This is the ownership backbone that makes a cross-remote,
multi-tree fleet safe and that separates "claimed" from "provisioned" so claiming can
happen long before a project is configured. Without it, two mnemes that both list a
shared tree, or a campaign copied between trees, become Split-Brain with no owner to
point to. Membership keeps ownership intrinsic to the campaign (Principle III) and
reconstructable (Principle IV).

**Independent Test**: Boot a fleet over two trees and confirm status lists the
discovered campaigns as un-integrated and writes to none of them. Run `mneme integrate`
on one and confirm exactly `.mneme/owner.yaml` appears (no provisioning artifacts).
Hand-edit a campaign's `owner.yaml` to a different mneme, boot again, and confirm it is
reported foreign-owned, not managed, not re-stamped. Recreate mneme with the same
identity, point it at the trees, and confirm it re-adopts only its own campaigns.

**Acceptance Scenarios**:

1. **Given** a discovered, un-integrated campaign, **When** boot/sync or status runs,
   **Then** it is reported as un-integrated and nothing is written to it.
2. **Given** an un-integrated campaign, **When** the operator runs `mneme integrate`,
   **Then** `.mneme/owner.yaml` is created naming this mneme, and no other provisioning
   artifacts are created.
3. **Given** a campaign owned by this mneme, **When** any operation runs, **Then** it is
   managed normally; `mneme up` provisions it (integrating first if needed).
4. **Given** a campaign whose `owner.yaml` names a *different* mneme, **When** integrate,
   bring-up, or any operation runs, **Then** it is not managed and not re-stamped, and it
   is surfaced (e.g. in status) as foreign-owned needing a decision.
5. **Given** `hypostasis.yaml` has no mneme identity yet, **When** mneme first needs it,
   **Then** a stable identity is minted once and persisted, and used for all claims.
6. **Given** a campaign moved from one declared tree to another, **When** discovery runs,
   **Then** its `owner.yaml` still names the same mneme (ownership travels with the
   campaign).

---

### User Story 5 - Owner is a logical identity, not a machine (Priority: P3)

The owning mneme is a logical fleet identity that can be present on more than one
hypostasis runtime / physical machine. `owner.yaml` never names a host. A campaign is
"mine" when its owner identity matches this runtime's mneme identity, regardless of
which machine the runtime is on — so that, in the long run, a campaign can be brought up
by a hypostasis on a different physical machine simply because that runtime carries the
same identity. (Executing cross-machine bring-up end-to-end is forward-looking; this
feature only guarantees the ownership model that makes it possible.)

**Why this priority**: It is the long-run goal behind the owner concept, and it is what
forces the identity to be host-independent (no Infrastructure Proxy). Getting the data
model right now is cheap; retrofitting host-coupling out later is not. The full
cross-machine bring-up flow is a future feature, so this story is scoped to the model
guarantee, not the execution.

**Independent Test**: Inspect a claimed campaign's `owner.yaml` and confirm it contains
no host/machine/path coordinate — only the logical identity. Configure a second runtime
with the same mneme identity and confirm it classifies the campaign as owned (not
foreign); configure it with a different identity and confirm foreign-owned.

**Acceptance Scenarios**:

1. **Given** a claimed campaign, **When** its `owner.yaml` is inspected, **Then** it
   names only the logical mneme identity (and optional label), with no host coordinate.
2. **Given** two runtimes configured with the *same* mneme identity, **When** each is
   pointed at the tree, **Then** both classify the campaign as owned-by-this-mneme.
3. **Given** a runtime with a *different* identity, **When** pointed at the tree, **Then**
   it classifies the campaign as foreign-owned (US4).

---

### User Story 6 - Resolve the toee split-brain (Priority: P3)

The operator has toee checked out as its own tree (`~/toee/toee`) while a stale copy
also sits inside the monorepo (`~/campaigns/toee`). The operator wants mneme to manage
toee from its own tree and stop treating the monorepo copy as authoritative — by
declaring the toee tree in the managed set and removing/ignoring the duplicate, with no
hand-edited paths buried in component logic.

**Why this priority**: This is the concrete operational payoff and the acid test, but
it is a consequence of US1–US5 rather than new machinery. It validates the feature
against the real situation that motivated it.

**Independent Test**: Declare the monorepo tree and the toee tree. Confirm toee is
discovered and managed from its own tree. With both copies present, confirm the
duplicate is surfaced (US3 ambiguity if both owned, or US4 foreign-owned), and that
resolving it requires only editing the declared-trees list — no other manual path edits.

**Acceptance Scenarios**:

1. **Given** the toee tree is declared and the monorepo no longer contains a toee
   campaign, **When** discovery runs, **Then** toee is managed from its own tree.
2. **Given** both copies are present and owned by this mneme, **When** a name-based toee
   command runs, **Then** the US3 ambiguity error fires, telling the operator exactly
   which duplicate to remove.

---

### Edge Cases

- **Same name in two trees (both owned)**: explicit ambiguity error on name-based
  resolution (US3); fleet-wide operations still list both, each by full path.
- **Discovered but un-integrated campaign**: reported as un-integrated by status/boot;
  nothing is written to it until the operator runs `mneme integrate` (or `mneme up`).
- **Foreign-owned campaign** (`owner.yaml` names another mneme): surfaced, never
  managed, never re-stamped (US4).
- **A declared tree path does not exist / is not a directory**: a configuration error,
  reported up front with any other config problems (all at once), before any work.
- **Declared trees that overlap or nest** (one inside another): rejected as a
  configuration error so a campaign is never discovered twice.
- **An empty tree** (no campaigns): contributes nothing; not an error.
- **Offline / no fetched git state**: discovery, status, integrate, and bring-up still
  work — mneme reads/writes the on-disk checkout and never reaches the network.
- **No mneme identity in config yet**: minted once on first need and persisted.
- **`mneme up` on an un-integrated campaign**: integrates it first (explicit, single
  campaign), then provisions; on a foreign-owned campaign it refuses.
- **Operations intrinsically tied to one tree** (e.g. listing pending integration
  proposals from a tree's git origin): act per-tree, never assume one global tree.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The managed campaigns location MUST be expressible as a list of one or
  more independent trees (managed roots) under a single parent the operator controls.
- **FR-002**: The previous single-value shape for the campaigns location MUST still be
  accepted and MUST behave as a one-tree fleet (backward compatibility).
- **FR-003**: Fleet-wide discovery MUST enumerate campaigns across **all** declared
  trees, applying the existing per-tree rule (a tree's immediate subdirectories are its
  campaigns) uniformly to each tree.
- **FR-004**: Every declared tree path MUST be validated (absolute after expansion,
  exists, is a directory, non-overlapping with other declared trees); violations MUST be
  reported together as configuration errors before any side effect.
- **FR-005**: Resolving a campaign by name MUST search the campaigns this mneme owns
  across all declared trees; if the name is present under more than one tree, resolution
  MUST fail with an explicit ambiguity error naming the campaign and every tree it was
  found in, and MUST NOT perform any side effect. Foreign-owned copies are excluded from
  resolution and surfaced separately.
- **FR-006**: Resolving a campaign by name that matches no declared tree MUST fail with
  a clear not-found error that lists the trees searched.
- **FR-007**: mneme MUST NOT clone, fetch, sparse-checkout, or otherwise drive git on
  any tree. It observes the live on-disk checkout; provisioning trees is the operator's
  responsibility (Silicon Truth). Writing mneme's own `.mneme/` artifacts into a
  campaign is not a git operation and is permitted.
- **FR-008**: All campaign operations (status, refresh, render, backup/restore,
  bring-up, MCP resolution) MUST behave identically regardless of which declared tree a
  campaign lives in.
- **FR-009**: Operations intrinsically scoped to a single tree (e.g. listing pending
  proposal branches from a tree's git origin, or publishing through version control)
  MUST operate per declared tree and MUST NOT assume one global tree.
- **FR-010**: Discovery ordering MUST be deterministic and stable across runs so that
  status output and downstream consumers do not churn.
- **FR-011**: The list shape for the campaigns location MUST live in the one
  configuration authority — it introduces no second writable store.
- **FR-012**: mneme MUST have a stable identity — a generated unique id, optionally with
  a human-readable label — persisted in its one configuration authority, minted once if
  absent and stable thereafter. The identity MUST NOT encode a host/machine coordinate.
- **FR-013**: A campaign's ownership MUST be recorded in a small self-contained
  `.mneme/owner.yaml` inside the campaign, naming the owning mneme. This record is the
  campaign's own declaration of ownership (Intrinsic State), is distinct from the
  indexing authority (`mempalace.yaml`) so it can exist before bring-up, and contains no
  host/machine coordinate.
- **FR-014**: Fleet boot/sync and read-only status MUST NOT write to any campaign. They
  MUST report each campaign's membership state — owned-by-this-mneme, foreign-owned, or
  un-integrated (no `owner.yaml`) — and MUST NOT claim campaigns automatically.
- **FR-015**: A campaign whose `owner.yaml` names a *different* mneme MUST NOT be managed
  or re-stamped by integrate, bring-up, or any operation; it MUST be surfaced as
  foreign-owned, requiring an explicit operator decision — no silent take-over, no
  silent skip.
- **FR-016**: `mneme integrate <campaign>` MUST claim an un-integrated campaign by
  writing `.mneme/owner.yaml` with this mneme's identity and performing no other
  provisioning. It MUST be idempotent on a campaign already owned by this mneme and MUST
  refuse a foreign-owned campaign (FR-015).
- **FR-017**: `mneme up` MUST operate only on a campaign owned by this mneme; if the
  campaign is un-integrated it MUST integrate it (claim) as its first stage before
  provisioning, and MUST refuse a foreign-owned campaign.
- **FR-018**: Ownership MUST be reconstructable from the campaigns themselves: a runtime
  carrying this mneme's identity, pointed at the trees, re-adopts exactly its own
  campaigns from their `owner.yaml` records, with no separate side registry (Brick Test).
- **FR-019**: The mneme identity MUST be a logical fleet identity that MAY be present on
  more than one hypostasis runtime / physical machine. Ownership MUST be determined by
  identity match alone, never by host, so that a campaign owned by an identity is
  recognized as owned by any runtime carrying that identity. (Executing cross-machine
  bring-up end-to-end is out of scope for this feature; the data model MUST NOT preclude
  it.)

### Key Entities *(include if feature involves data)*

- **Managed root (tree)**: a directory mneme scans for campaigns. One or more are
  declared. A tree is an infrastructure coordinate (a checkout location), not an
  identity — its remote, sparseness, and on-disk path are observed, never assumed.
- **Campaign**: an immediate subdirectory of a tree. Has a lifecycle: *discovered*
  (found, read-only) → *integrated/owned* (claimed via `owner.yaml`) → *provisioned*
  (brought up). Its identity and ownership travel with it (Intrinsic State), independent
  of which tree or machine currently hosts it.
- **mneme identity**: the owning fleet's stable, generated, host-independent id plus an
  optional human-readable label, persisted in the one configuration authority. The same
  logical identity may run on multiple machines.
- **Campaign membership record (`.mneme/owner.yaml`)**: a small self-contained record
  inside a campaign naming the owning mneme, with no host coordinate. Distinct from the
  indexing authority (`mempalace.yaml`) so it can exist for a campaign that has not yet
  been brought up.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With two trees declared, a single fleet-wide status run lists 100% of the
  campaigns from both trees, each with correct path, authority status, and membership
  state.
- **SC-002**: An existing single-location configuration produces byte-for-byte the same
  discovery and status results before and after the feature (zero regressions).
- **SC-003**: 100% of duplicate-name-across-trees cases (among owned campaigns) produce
  an explicit ambiguity error naming every conflicting tree; 0% silently resolve to one
  tree.
- **SC-004**: The toee split-brain is resolvable by editing only the declared-trees list
  (adding the toee tree, removing the duplicate) — no other manual path edits, no
  changes to component logic.
- **SC-005**: Discovery and status complete with no network access and zero writes to any
  campaign or git tree (verifiable by running offline and confirming every tree's state
  is unchanged).
- **SC-006**: After a boot/sync over the declared trees, status correctly reports every
  un-integrated campaign and every foreign-owned campaign, and boot/sync has written to
  zero campaigns.
- **SC-007**: `mneme integrate` on an un-integrated campaign produces exactly
  `.mneme/owner.yaml` and no other artifacts; a later `mneme up` completes provisioning.
- **SC-008**: A runtime with the preserved identity, pointed at the trees, re-adopts
  exactly its own campaigns from their `owner.yaml` records with no central registry
  consulted; a runtime with a different identity classifies them as foreign-owned.
- **SC-009**: No claimed campaign's `owner.yaml` contains a host/machine/path coordinate
  (verifiable by inspection across all claimed campaigns).

## Assumptions

- The operator provisions trees (clone, sparse-checkout, fetch) by hand or by their own
  tooling; mneme only observes the result (mneme does not drive git).
- The only writers of `.mneme/owner.yaml` are the explicit `mneme integrate` and
  `mneme up`; fleet boot/sync and read-only status never write to a campaign.
- `mneme up` integrates (claims) an un-integrated campaign as its first stage; both
  `integrate` and `up` refuse a foreign-owned campaign.
- The membership record is the file `.mneme/owner.yaml`, distinct from the indexing
  authority (`mempalace.yaml`). Its exact fields are a plan-phase concern, but it carries
  the logical owner identity and no host coordinate.
- mneme identity is a generated unique id (with optional human label) persisted in
  `hypostasis.yaml`; the same logical identity may be configured on multiple machines,
  and preserving it across machines/restores preserves ownership.
- Full cross-machine bring-up execution is a future feature; feature 005 guarantees only
  the host-independent ownership model that enables it.
- Each campaign lives in exactly one tree. A campaign does not span trees; duplicate
  names across trees are a condition to resolve (US3), not a supported topology.
- Declared trees are not nested inside one another; overlapping declarations are a
  configuration error.
- The per-campaign indexing authority and store-pointer model (feature 003) is
  unchanged; this feature changes where mneme *looks* for campaigns and adds an ownership
  record + claim step, not how a campaign is indexed once managed.
- The "one parent directory holding many trees" is realized as the declared list of tree
  paths; the parent itself is a convenience for the operator, not a scanned root.
