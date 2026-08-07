# Feature Specification: Portable vs Host-Local Campaign State

**Feature Branch**: `006-portable-campaign-state`

**Created**: 2026-08-07

**Status**: Draft

**Input**: User description: "Portable vs host-local campaign state (GH #51). A campaign repo is shared across two machines via git, but mneme writes host-local values into the two always-tracked `.mneme/` files, so the second machine cannot manage its own campaigns and every render produces a spurious diff. Two parts, one decision — what does mneme consider portable across hosts? PART A: the mneme fleet identity must actually be portable. Today the identity is minted lazily per host, so each machine mints its own and classifies the other's campaigns foreign; the only workaround bypasses the ownership gate off-label. Fix: when a host has no identity, mneme must read the ownership records already present in the declared trees and, if they name exactly one owner, refuse to mint and tell the operator to adopt that identity (or mint deliberately); mint only when there is nothing to adopt; refuse and list the choices when more than one owner is present. Add an identity command group (show | adopt | mint). The foreign-owner error message must name both identities and the remedy. No silent take-over. PART B: the store path must stop being tracked. The authority requires it absolute and re-serializes the expansion, so the tracked file flips between two hosts' home directories forever. Fix: the tracked authority carries the store alias only; the palace location is derived at run time from a host-configured root plus the alias. A legacy stored path that matches the derived value is accepted and reported as owed work; one that differs is a hard error naming both."

## Overview

A campaign workspace travels between machines through git. Two of the files mneme
writes into that workspace are **always tracked** — the indexing authority
(`.mneme/mempalace.yaml`) and the ownership record (`.mneme/owner.yaml`) — and both
currently carry values that are only true on the machine that wrote them. The result
is that a second machine cannot manage campaigns it legitimately owns, and every
operation on either machine produces a diff that the other machine will "correct"
back.

Feature 005 established the axis **derived vs authority**: derived files are caches
rendered from an authority, the authority is hand-editable truth. This feature adds
the axis that 005 missed — **portable vs host-local** — and that axis cuts *through*
the authority file rather than between files. `campaign`, `recipe_version`, `wings`,
and the store *alias* are portable; the store *path* and the minting of the fleet
identity are not.

The decision this feature makes: **anything a campaign carries in git must be true on
every machine that checks it out.** A value that is only true on one host belongs in
that host's configuration authority, or is derived at run time — never in the campaign.

## Clarifications

### Session 2026-08-07

- Q: When a campaign's tracked authority carries a legacy store path that *conflicts* with
  the derived location, what does that block? → A: Every operation, including load. The
  authority is unloadable until the field is removed; fleet status shows the campaign as
  invalid-config naming both locations, and reports no other dimension for it.
- Q: Does a host need a per-alias store location override for a palace that must live
  somewhere other than the derived location? → A: No. Derivation is the only resolution
  rule; the filesystem is the escape hatch — symlink the derived location at the real one.
  No override map in host configuration.
- Q: Should the 005 workspace-path override stop bypassing the ownership gate? → A: Yes.
  Ownership classification moves out of name resolution and applies however the campaign
  was named, so the override once again means only "disambiguate the tree." No named
  opt-out flag is added.
- Q: How is a duplicate store alias across two campaigns surfaced? → A: Hard error on any
  operation touching either campaign, naming both campaigns and the shared alias. Alias
  uniqueness is a fleet-level invariant, so a single-campaign command must consult
  discovery to enforce it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A second machine manages the campaigns it owns (Priority: P1)

The operator runs mneme on two machines against the same campaign checkout. Both
machines belong to the same logical fleet. On the second machine, every campaign
command that takes a campaign *name* must work — the same way, with the same result,
and without needing an escape-hatch flag.

Today the second machine mints its own fleet identity the first time it needs one, so
every campaign in the shared checkout names an identity that machine does not have, and
every name-based command refuses.

**Why this priority**: This is the reported failure and the reason for the feature.
Until it is fixed the second machine is not a fleet member at all — it can only operate
by bypassing the ownership gate.

**Independent Test**: On a machine with no fleet identity, point mneme at a tree
containing campaigns owned by a known identity. Verify mneme refuses to invent a new
identity, names the one it found, and offers to adopt it; then adopt it and verify
every name-based command resolves the campaigns as owned.

**Acceptance Scenarios**:

1. **Given** a host with no fleet identity and declared trees whose campaigns all name
   one identity, **When** mneme needs an identity, **Then** it does **not** mint one; it
   reports the identity it found, how many campaigns carry it, and the two explicit
   remedies (adopt that identity, or mint a new one deliberately).
2. **Given** that host, **When** the operator adopts the found identity, **Then** the
   identity is persisted in the host's configuration authority, and every campaign that
   names it is thereafter classified as owned by this mneme.
3. **Given** a host that has adopted the fleet identity, **When** the operator runs any
   name-based campaign command, **Then** it resolves and succeeds without an explicit
   workspace-path override.
4. **Given** a host with no fleet identity and declared trees containing **no**
   ownership records at all, **When** mneme needs an identity, **Then** it mints one and
   says so — the greenfield case is unchanged.
5. **Given** declared trees whose campaigns name **more than one** identity, **When**
   mneme needs an identity, **Then** it refuses, lists each identity with the campaigns
   carrying it, and requires an explicit operator choice.

---

### User Story 2 - The tracked authority is identical on every machine (Priority: P1)

The operator inspects a campaign's authority file on both machines and sees byte-identical
content. Running a render, a status, or a bring-up on either machine leaves the tracked
files unchanged, so the shared repository never accumulates a diff whose only content is
"which machine ran last."

Today the authority records the store location as an absolute path. One machine writes
its home directory, the other machine reads it, fails to use it, "fixes" it to its own
home directory, and commits — forever.

**Why this priority**: Equal in severity to US1 and independent of it. Even a correctly
identified fleet member cannot share a repository while the authority encodes a home
directory. It is separately testable and separately valuable.

**Independent Test**: Write an authority on one host, read it on a host with a different
home directory, and verify the two hosts resolve **different** store locations from
**identical** file content — and that neither host rewrites the file.

**Acceptance Scenarios**:

1. **Given** an authority written by mneme, **When** it is serialized, **Then** it
   contains the store **alias** and no store path.
2. **Given** identical authority content read on two hosts with different home
   directories, **When** each resolves the campaign's store, **Then** each resolves to a
   location under its **own** host-configured root, and the file content is unchanged on
   both.
3. **Given** a host that declares no store root, **When** a campaign's store is resolved,
   **Then** a documented default root is used, so an existing single-host setup needs no
   configuration change.
4. **Given** a host that declares a non-default store root, **When** a campaign's store is
   resolved, **Then** the declared root is used for every campaign on that host.

---

### User Story 3 - Legacy authorities are surfaced, never silently re-pointed (Priority: P2)

Campaigns already in the fleet carry a stored path written by the old behavior. The
operator must be told that the field is owed cleanup, and must be protected from the
one dangerous case: a stored path that points somewhere the new derivation would **not**
resolve to, where silently switching would abandon a real store full of real content.

**Why this priority**: This is the migration safety property. It is lower priority than
US1/US2 because it protects the transition rather than delivering the capability, but
skipping it risks silently orphaning an existing index.

**Independent Test**: Load an authority carrying a stored path equal to the derived
location and verify it loads with the field reported as owed work; load one carrying a
different path and verify it fails with an error naming both locations.

**Acceptance Scenarios**:

1. **Given** an authority carrying a stored path **equal** to the derived location,
   **When** it is loaded, **Then** it loads successfully and the fleet status reports the
   field as owed cleanup on that campaign.
2. **Given** an authority carrying a stored path **different** from the derived location,
   **When** any operation on that campaign runs — read-only ones included — **Then** it
   fails before any side effect with an error naming both the stored and the derived
   location.
3. **Given** that same campaign, **When** the fleet status runs, **Then** the campaign is
   reported as invalid-config with both locations named, every other campaign is reported
   in full, and the run does not fail as a whole.
4. **Given** an authority whose stored path has been removed, **When** it is loaded,
   **Then** it loads cleanly and the status no longer reports owed cleanup.

---

### User Story 4 - The foreign-owner refusal tells the operator what to do (Priority: P3)

When mneme refuses a campaign because it names a different owner, the message must
name the owning identity, name this mneme's identity, and state the remedy. Today it
names neither this mneme's identity nor any remedy, so the only way forward is reading
the source.

**Why this priority**: Observability polish on a path that US1 makes rare. Valuable
because the refusal is still correct behavior in the genuinely-foreign case, and a
correct refusal that points nowhere is indistinguishable from a bug.

**Independent Test**: Classify a campaign owned by a different identity on a host that
has its own identity, and verify the resulting message contains both identities and a
named next step.

**Acceptance Scenarios**:

1. **Given** a campaign naming a different owner, **When** any command refuses it,
   **Then** the message names the campaign's owner, this mneme's identity, and the
   remedy.
2. **Given** a campaign naming a different owner, **When** the operator supplies the
   workspace-path override, **Then** it is refused with the same message — the override
   selects a workspace, it does not confer ownership.
3. **Given** a host with no identity at all, **When** status reports a campaign's
   membership, **Then** it says the identity is not established and points at the
   adopt-or-mint choice rather than at minting alone.

---

### Edge Cases

- **A campaign is genuinely foreign.** Adoption of a fleet identity must never be
  inferred from a campaign that the operator did not intend to claim. Mneme surfaces
  what it found and stops; it does not adopt on its own.
- **The host already has an identity that owns campaigns.** Adopting a different identity
  would orphan them. Adoption refuses in that case unless the operator forces it, and the
  refusal names the campaigns at risk.
- **The declared trees are unreachable or empty.** A tree that is not checked out
  contributes nothing and must not wedge the identity decision (Principle VI, federated).
- **Two campaigns declare the same store alias.** They resolve to the same location. Since
  the alias defaults to the campaign name, this is exactly the case where one campaign name
  exists under two declared trees — the ambiguity 005 already refuses to resolve, now with a
  second reason to refuse it.
- **A stored path differs only by symlink or trailing separator.** Comparison must resolve
  both locations before declaring a conflict, so a sanctioned symlink redirect (FR-011a)
  never reads as a mismatch under FR-014.
- **Adoption is attempted with a malformed identity value.** It is rejected before the
  host's configuration authority is touched.

## Requirements *(mandatory)*

### Functional Requirements

**Fleet identity portability**

- **FR-001**: The fleet identity MUST be establishable on a host by **adopting** an
  existing identity, not only by minting a new one. Adoption MUST persist it in the host's
  one configuration authority, preserving the operator's existing file content.
- **FR-002**: When a host has no fleet identity and mneme needs one, mneme MUST first
  observe the ownership records present in the declared trees and MUST NOT mint an
  identity when exactly one distinct owner is found there. It MUST instead report that
  owner, the campaigns carrying it, and both remedies (adopt / mint).
- **FR-003**: When the declared trees contain **no** ownership records, mneme MUST mint an
  identity and report the minted value — the greenfield behavior is preserved.
- **FR-004**: When the declared trees contain **more than one** distinct owner, mneme MUST
  refuse, list each owner with the campaigns carrying it, and require an explicit choice.
- **FR-005**: mneme MUST NOT adopt an identity automatically under any circumstance. Every
  adoption is an explicit operator action (no silent take-over — 005 FR-015).
- **FR-006**: Operators MUST be able to inspect the current fleet identity, adopt a named
  identity, and mint a new identity as three distinct, discoverable operations.
- **FR-007**: Adopting an identity on a host whose current identity **already owns**
  campaigns in the declared trees MUST be refused unless the operator explicitly overrides,
  and the refusal MUST name the campaigns that would be orphaned.
- **FR-008**: Establishing or changing the fleet identity MUST NOT write to any campaign.
- **FR-009**: Every refusal based on ownership MUST name the campaign's declared owner,
  this mneme's identity (or its absence), and the operator's next step.

**Store location portability**

- **FR-010**: The tracked campaign authority MUST NOT contain a machine-specific store
  location. Serializing an authority MUST emit the store **alias** and MUST NOT emit a
  store path.
- **FR-011**: A campaign's store location MUST be resolved at run time from a
  **host-configured store root** plus the campaign's store alias, and MUST be identical for
  a given host and alias regardless of which campaign or command resolved it.
- **FR-011a**: Root-plus-alias MUST be the **only** resolution rule. mneme MUST NOT offer a
  per-alias location override in any authority, host-local or tracked (Principle V — no
  parallel lookup table). Redirecting one palace is a filesystem concern: the derived
  location may be a symlink to the real one, and mneme MUST follow it transparently.
- **FR-012**: The store root MUST be declarable in the host's one configuration authority
  and MUST default to the location existing setups already use, so no existing single-host
  configuration requires an edit.
- **FR-013**: Reading an authority that carries a legacy stored path **equal** to the
  derived location MUST succeed, and the fleet status MUST report the field as owed
  cleanup for that campaign.
- **FR-014**: Reading an authority that carries a legacy stored path **different** from the
  derived location MUST fail before any side effect, with an error naming both locations.
  The failure MUST apply to **every** operation on that campaign, including read-only ones —
  the authority does not load at all until the field is removed. mneme MUST NOT silently
  re-point a campaign at a different store.
- **FR-014a**: Fleet status MUST remain usable when one campaign's authority is unloadable
  under FR-014: it MUST report that campaign as invalid-config with the message naming both
  locations, and MUST continue reporting every other campaign in full (Principle VI —
  one bad campaign is one failed row, not a wedged fleet).
- **FR-015**: Every store-naming face rendered for a campaign (the search-tool pointer, the
  global alias registry, the editor tool registration) MUST use the resolved location, so
  the "right store everywhere" property established in 003 continues to hold across hosts.
- **FR-016**: Two campaigns declaring the same store alias MUST fail any operation that
  touches either of them, with an error naming both campaigns and the shared alias. Neither
  campaign may read from or write to the contested store while the conflict stands.
- **FR-016a**: Alias uniqueness is a **fleet-level** invariant, so enforcing it on a
  single-campaign command requires that command to consult discovery across the declared
  trees. A workspace named by the path override that lies outside every declared tree is
  checked against the campaigns that are discoverable; no campaign is exempt from the check
  merely because it was named by path.

**Fleet-wide invariants**

- **FR-017**: Given identical tracked campaign files, two hosts differing only in
  host-local configuration MUST reach the same ownership conclusions and MUST produce **no**
  modification to any tracked file as a result of read-only or render operations.
- **FR-018**: Ownership MUST be enforced independently of how a campaign was named. A
  campaign naming a different owner MUST be refused whether it was resolved by name or by
  the 005 workspace-path override, which returns to meaning only "disambiguate which tree."
  There is no flag that operates on a foreign campaign.
- **FR-019**: The change in FR-018 removes the only workaround available today, so the
  identity remedy (FR-001/FR-006) MUST ship in the same release — no window may exist in
  which a legitimately-owned campaign is unmanageable by both routes.

### Key Entities

- **Fleet identity**: the logical, host-independent owner id (005 FR-012/019). Newly, it
  has a *lifecycle* — established by minting **or** adoption — rather than being minted
  implicitly on first use.
- **Campaign authority** (`.mneme/mempalace.yaml`): unchanged in role. Its store block
  narrows to the portable half — the alias.
- **Store root**: a **host-local** coordinate naming where this machine keeps its palaces.
  Lives in the host's configuration authority alongside the other data roots; never in a
  campaign.
- **Store pointer**: the campaign's alias plus the location derived from it. The location is
  a run-time value, not a stored one.
- **Ownership record** (`.mneme/owner.yaml`): unchanged. It is now also the *evidence* a
  host consults when deciding which identity to adopt.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a machine that has adopted the fleet identity, **100%** of name-based
  campaign commands that previously required a workspace-path override succeed without one.
- **SC-002**: Running the full read-only and render surface on either machine produces
  **zero** modified tracked files in the shared campaign repository.
- **SC-003**: A campaign authority written on one machine is **byte-identical** to the same
  authority written on the other, for the same campaign in the same state.
- **SC-004**: A host with no established identity, pointed at trees owned by one identity,
  produces a message that names that identity and both remedies — verifiable in **one**
  command, with no source reading required.
- **SC-005**: **Zero** code paths can write a machine-specific store location into a tracked
  file — enforced by the serializer, not by convention.
- **SC-006**: Both currently-affected campaigns in the live fleet are managed by name from
  both machines, with the shared repository showing no host-attributable churn thereafter.
- **SC-007**: An authority whose stored location conflicts with the derived one fails
  **before** any store is created, read, or written — never after.
- **SC-008**: **Zero** routes exist by which a foreign-owned campaign or an alias-conflicted
  campaign can be operated on — measured by exercising every campaign-naming route (by name
  and by workspace path) against both cases and observing a refusal each time.

## Assumptions

- The two machines in the reported failure are intended to be the **same** logical fleet.
  Making them separate fleets is a valid alternative outcome the operator can still choose
  by minting deliberately, but the default remedy this feature optimizes for is joining.
- Every palace on a host lives under one root, named by alias. No campaign in the fleet
  currently uses a bespoke store location, so alias-derivation loses no live capability.
  A palace that must sit elsewhere is redirected with a filesystem symlink at the derived
  location (FR-011a) — mneme itself has one resolution rule and no override table.
- The host configuration authority remains hand-editable and human-owned; adoption is a
  convenience over editing it, not a replacement for the operator's ownership of that file.
- Ownership **transfer** — re-homing a campaign from one fleet identity to another — is out
  of scope. This feature makes the *identity* portable; it does not add a supported way to
  change a campaign's declared owner. That remains the open question in GH #51's comment.
- Feature 003's dedicated-store-per-campaign model and 005's discovery/membership model are
  unchanged; this feature only relocates which side of the host boundary two values sit on.

## Dependencies

- **GH #35** (discovery follows symlinked campaign directories into the host filesystem and
  scans without bound) is a **hard** dependency, and the clarifications widened it. Three
  requirements now put a full tree scan on code paths that previously performed none:
  FR-002 (the identity decision reads ownership records across the trees), FR-016a (alias
  uniqueness is fleet-level), and FR-018 (path-named campaigns are no longer exempt from
  the checks that discovery feeds). On a host carrying such a symlink, all three hang.
  #35 must land before or with this feature.
- **GH #30** (whether derived faces are tracked at all) is **unblocked by** this feature and
  is explicitly out of scope: its proposed end-state concentrates fleet churn onto exactly
  the two files this feature makes portable.
- **Migration ordering.** Under FR-014 each host finds a *different* campaign fatal — the one
  whose tracked path names the other host's home directory — so shipping the code without
  removing the legacy field leaves every host with one unloadable campaign. The campaign-repo
  edit (removing the field) and the release are one deployment, not two.

## Out of Scope

- Executing a cross-machine bring-up end-to-end (already out of scope per 005 FR-019; this
  feature keeps the data model from precluding it).
- Ownership transfer / re-homing a campaign to a different fleet identity.
- Any change to what mempalace stores or how it embeds.
- The tracking policy for derived faces (GH #30).
