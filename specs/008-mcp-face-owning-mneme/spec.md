# Feature Specification: MCP Face Bound to the Owning mneme

**Feature Branch**: `008-mcp-face-owning-mneme`

**Created**: 2026-11-09

**Status**: Draft

**Input**: User description: "mneme#87 — mcp face never registers `mneme mp mcp`, and binds servers by PATH instead of to the owning mneme"

## Context

A host can run more than one mneme. Each mneme is defined by its own hypostasis config: its own
install (venv), its own mneme identity, and therefore its own mempalace. A campaign is owned by
exactly one mneme (its `owner` record names that mneme's identity).

mneme already renders an "mcp face" into each campaign: an assistant-session server list that
today contains a single `mempalace` server. Two defects (GH #87):

1. mneme's own advisory server (status, target config, corpus files, inventory, search,
   instructions) is never registered, so no assistant session in any campaign can reach it.
   Registering it once, user-wide, is wrong: a single entry is bound to one mneme and would answer
   for the wrong mneme and mempalace in every campaign that mneme does not own.
2. The `mempalace` server entry names its program by bare name, so whichever install comes first
   on the search path runs — possibly a different mneme's mempalace serving this campaign's palace.

Observed on toee: neither the campaign's server list nor the wrapper project's server list has a
`mneme` entry, and `mp status` reports the faces as "right store everywhere".

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The campaign's assistant session can reach its own mneme (Priority: P1)

A GM opens an assistant session for a campaign and asks it about the campaign's mneme state
(status, which files a corpus kind holds, a palace search). The session has a `mneme` server
available that is the mneme which owns this campaign, using that mneme's config, with no manual
registration.

**Why this priority**: This is the reported gap. Without it, the advisory server shipped in #85
is unusable from campaign sessions.

**Independent Test**: Render the faces for a campaign owned by mneme A; the campaign's server list
contains a `mneme` entry that launches mneme A's program with mneme A's config. Starting that entry
and calling its status tool returns this campaign's status.

**Acceptance Scenarios**:

1. **Given** a campaign owned by this mneme with no `mneme` server entry, **When** the GM
   re-renders its faces, **Then** the server list gains a `mneme` entry naming this mneme's own
   program by absolute location and this mneme's config file by absolute location.
2. **Given** the server list already holds other servers (e.g. `campaign`, `5etools`), **When** the
   faces are re-rendered, **Then** those entries are preserved unchanged.
3. **Given** the rendered `mneme` entry, **When** an assistant session starts it, **Then** the
   server starts without relying on the search path or the session's working directory to find
   either the program or the config.

---

### User Story 2 - The palace server is pinned to the owning mneme's mempalace (Priority: P1)

The `mempalace` server entry names the owning mneme's mempalace server program by absolute
location, so the palace is always served by the mempalace that built it.

**Why this priority**: Same root cause as Story 1 and silently wrong today — the right palace
path served by possibly the wrong mempalace version or backend.

**Independent Test**: Put a different `mempalace-mcp` first on the search path; the rendered entry
still names the owning mneme's program.

**Acceptance Scenarios**:

1. **Given** a campaign owned by this mneme, **When** faces are rendered, **Then** the `mempalace`
   entry's program is the absolute location of the owning mneme's mempalace server program, and its
   palace path and allowed embedder/backend settings are unchanged from today.
2. **Given** the owning mneme's install has no mempalace server program, **When** faces are
   rendered, **Then** rendering fails loudly naming the missing program, rather than writing an
   entry that falls back to the search path.

---

### User Story 3 - Status reports a missing or foreign server entry (Priority: P2)

`mp status` treats both server entries as part of face coherence. A missing `mneme` entry, or an
entry (either server) whose program or config belongs to a different mneme, is reported as an
incoherent face with a concrete reason and the fix (`mp faces`).

**Why this priority**: Principle IX — the toee gap existed because status said "right store
everywhere" while the server was absent. Detection prevents silent recurrence; the render alone
does not. The fix status names is `mp faces`.

**Independent Test**: Delete the `mneme` entry from a rendered campaign; `mp status` reports the
faces row as not coherent naming the `mneme` entry. Re-render; status is coherent again.

**Acceptance Scenarios**:

1. **Given** a campaign with no `mneme` entry, **When** the GM runs `mp status`, **Then** the faces
   row is not coherent and names the missing `mneme` entry.
2. **Given** a `mneme` entry whose program or config is another mneme's, **When** status runs,
   **Then** the faces row is not coherent and names which value differs.
3. **Given** a `mempalace` entry naming its program by bare name (today's render), **When** status
   runs, **Then** the faces row is not coherent, so every existing campaign surfaces the upgrade.
4. **Given** a freshly rendered campaign, **When** status runs, **Then** the faces row is coherent.

---

### User Story 4 - The session opened at the clone root loads the face (Priority: P2)

Campaigns are checked out as sparse clones of the shared campaigns repository: the clone root
(e.g. `~/toee`) holds shared material (`.claude/`, `gm-assistant/`, `scripts/`) plus one campaign
directory (`~/toee/toee`). Assistant sessions open at the clone root, so a face rendered only into
the campaign directory is never loaded. Verified on this host: all five managed campaigns are
single-campaign sparse clones laid out this way.

The rule depends on how many campaigns the clone holds:

- **Exactly one campaign in the clone** → mneme also renders the `mneme` and `mempalace` entries
  into the clone root's server list, and status checks that copy too.
- **More than one campaign in the clone** → mneme writes nothing at the root (there is no single
  palace the root could point at). Status reports that sessions opened at the root will not have
  this campaign's servers.
- **More than one campaign, and the root's server list already has mneme-owned entries** (someone
  sparse-checked out a second campaign into a configured clone) → this is a misconfiguration, not
  a supported layout. Status announces it as a FAIL naming the campaigns and the entries, and mneme
  changes nothing at the root.

**Why this priority**: Without it, Stories 1–2 change files no session on this host ever loads:
SC-005 fails for every campaign.

**Independent Test**: In a single-campaign sparse clone, render faces; the clone root's server
list gains both entries, and other entries are untouched. Add a second campaign to the sparse
checkout; status reports the misconfiguration, and a re-render leaves the root file byte-identical.

**Acceptance Scenarios**:

1. **Given** a sparse clone whose working tree holds exactly one campaign, owned by this mneme,
   **When** faces are rendered, **Then** both entries are written to the campaign directory's
   server list and to the clone root's server list, and every other root entry is preserved.
2. **Given** that single-campaign clone, **When** status runs after the root entries are removed or
   changed, **Then** the faces row is not coherent and names the root server list.
3. **Given** a clone whose working tree holds two or more campaigns and a root server list with no
   mneme-owned entries, **When** faces are rendered, **Then** nothing is written at the root, and
   status reports (as to-do, not FAIL) that root-opened sessions will lack the campaign's servers.
4. **Given** a clone holding two or more campaigns whose root server list already has a `mneme` or
   `mempalace` entry, **When** faces are rendered or status runs, **Then** status reports a FAIL
   naming the campaigns in the clone and the root entries, and the root file is not modified.
5. **Given** a campaign directory that is itself the repository root (no enclosing clone), **When**
   faces are rendered, **Then** behaviour is exactly Stories 1–3; there is no separate root copy.

---

### Edge Cases

- **Two mnemes on one host**, each owning a campaign: each campaign's entries name its own owner's
  program and config; rendering from mneme A never touches a campaign owned by mneme B.
- **A campaign owned by another mneme** (FOREIGN): this mneme refuses it, as every `mp` route
  already does, and never renders or rewrites its server entries. An UNINTEGRATED campaign (e.g.
  during bring-up) is rendered as today (research R2).
- **The owning mneme's program location moves** (venv rebuilt elsewhere, config file moved):
  status reports the entries stale; re-rendering repairs them.
- **The server list file is unreadable or not valid JSON**: rendering fails loudly and does not
  overwrite it; status reports it.
- **A hand-added `mneme` entry the GM customized**: it is a rendered (mneme-owned) entry; a
  re-render replaces it. Other server names are never touched.
- **Secrets**: no credential or API key is ever written into either entry; only the existing
  allow-listed embedder/backend settings reach the `mempalace` entry, and the `mneme` entry carries
  no environment settings beyond what it needs to start.
- **A hand-added `mneme` entry already at a single-campaign clone root** (true today for
  `~/obelisk`): it is a mneme-owned name, so the render replaces it with the owning mneme's values;
  the other root entries are untouched.
- **A clone holding campaigns owned by different mnemes**: this counts as a multi-campaign clone
  (FR-012/FR-013); no mneme writes at the root.
- **Campaign with no store pointer**: today the mcp face is skipped entirely; the `mneme` entry
  does not depend on a store, so it is still rendered (status, corpus and instructions work without
  a palace).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The mcp face MUST include a `mneme` server entry for every campaign the rendering
  mneme manages (not FOREIGN to it; research R2).
- **FR-002**: The `mneme` entry MUST launch the owning mneme's own program, named by absolute
  location, with the owning mneme's config named by absolute location. It MUST NOT depend on the
  search path or the session's working directory.
- **FR-003**: The `mempalace` entry MUST name the owning mneme's mempalace server program by
  absolute location. Its palace path and allowed environment settings remain as today (GH #26).
- **FR-004**: Both program locations MUST be derived from the owning mneme's declared config
  (its install location and config file), never hardcoded in component logic (Principle II).
- **FR-005**: If either program does not exist at the derived location, rendering MUST fail with an
  error naming the missing program and MUST NOT write a partial or search-path entry.
- **FR-006**: Rendering MUST preserve every other server entry in the file, byte-for-byte in value.
- **FR-007**: Face coherence (as reported by `mp status`) MUST check the `mneme` entry for presence,
  program and config, and the `mempalace` entry's program, in addition to today's palace-path and
  environment checks; each mismatch MUST be reported as a distinct, named reason.
- **FR-008**: The `mneme` entry MUST be rendered even when the campaign has no store pointer.
- **FR-009**: The `mneme` entry MUST NOT carry secrets; the existing environment allow-list
  continues to govern the `mempalace` entry.
- **FR-010**: `mp faces` (and bring-up, which renders faces) MUST repair any incoherence reported
  by FR-007/FR-011 with no other manual step. `mp refresh` stays a mining command and does not
  render faces; status names `mp faces` as the fix.
- **FR-011**: When the campaign directory sits inside an enclosing repository working tree (the
  clone root) that holds exactly one campaign, rendering MUST also write both mneme-owned entries
  into the clone root's server list, with the same values and the same preservation rule (FR-006),
  and coherence MUST check that copy.
- **FR-012**: When the clone root's working tree holds more than one campaign, rendering MUST NOT
  write to the clone root's server list. Status MUST report that root-opened sessions lack the
  campaign's servers (to-do).
- **FR-013**: When the clone root's working tree holds more than one campaign AND the clone root's
  server list already contains a `mneme` or `mempalace` entry, status MUST report a FAIL
  (misconfiguration) naming the campaigns and the entries, and no command may modify the root file.
- **FR-014**: "Campaigns in the working tree" MUST be counted from what is actually checked out
  (the observed sparse working tree), not from what the shared repository contains.
- **FR-015**: A checked-out top-level folder of the clone counts as a campaign unless its name is
  in the host's declared **shared set** (the non-campaign folders such as `gm-assistant`,
  `scripts`), declared in the hypostasis config (GM decision 2026-11-09). Dot-folders never count.
- **FR-016**: If the host declares no shared set, mneme MUST NOT write at the clone root (it cannot
  count reliably) and status MUST report the missing declaration as a to-do naming the folders it
  found.

### Key Entities

- **Owning mneme**: the mneme whose identity a campaign's owner record names; defined by one
  config file, which declares its install location and identity.
- **MCP face**: the campaign's host-local, untracked assistant server list; mneme owns the `mneme`
  and `mempalace` entries in it and nothing else.
- **Server entry**: a named launch description — program, arguments, environment.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After `mp faces` for each campaign, every managed campaign on this host (phandalin,
  out-of-the-abyss, obelisk, toee, greenwold) has a `mneme` entry and an absolutely-pinned
  `mempalace` entry, both in the campaign directory and at its single-campaign clone root, and
  `mp status` reports their faces coherent.
- **SC-006**: Adding a second campaign to a configured sparse clone produces a FAIL on the next
  `mp status`, and 0 bytes of the clone root's server list change.
- **SC-002**: With a decoy `mempalace-mcp` placed first on the search path, 100% of rendered
  entries still name the owning mneme's programs.
- **SC-003**: In a two-mneme test setup, 0 campaigns have an entry naming the non-owning mneme.
- **SC-004**: Removing or corrupting either entry is detected by the next `mp status` in 100% of
  cases (no silent "coherent" result).
- **SC-005**: A GM can ask a campaign session for that campaign's mneme status and get an answer
  with zero manual server registration.

## Assumptions

- The campaign's server-list file is host-local and git-ignored (verified for toee: both the
  campaign's and the wrapper's are ignored), so absolute host paths in it are acceptable — the
  existing face already writes absolute palace paths and endpoints.
- A mneme's install location (its venv) holds both the mneme program and the mempalace server
  program; this is how mneme is installed today.
- `mneme mp mcp` already accepts the config file location as an argument and serves any campaign
  named in a tool call; this feature does not change the server's tools.
- The other campaign-side servers (`campaign`, `5etools`, `registry`, `provenance`) are out of
  scope; they are not mneme-owned and keep resolving however they do today.
- The existing campaigns are upgraded by running `mp faces` per campaign; no migration branch is
  needed because the face (including the clone root's server list) is untracked.
- Out of scope, separate issue: how campaign clones are created. Today a sparse clone is set up by
  hand, and a full checkout of the campaigns repository (every campaign in one working tree) is
  possible, but it is a weird layout, not a supported one. A scripted single-campaign sparse
  checkout, or a different way of managing the campaign repositories, belongs in its own issue.
  This feature only detects the multi-campaign case; it does not prevent or repair it.
  Tracked as kostadis/campaigns#672.
