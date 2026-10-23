# Feature Specification: Declared Campaign Corpus

**Feature Branch**: `007-declared-campaign-corpus`

**Created**: 2026-10-23

**Status**: Draft

**Input**: User description: "Declared campaign corpus — one agreed file set for every search consumer. I don't want mempalace to look at one file, Claude at another, and CampaignGenerator at a third. Rather than having to 'fix' the location of files, have a configuration file that says: party files — and then I provide a directory or a list of files; similarly for summaries and for NPC data."

## Clarifications

### Session 2026-10-23

- Q: Where do prep and PC data live? → A: Not a spec decision. The corpus is declared by
  kind; each campaign maps each kind to a directory or a list of files wherever they
  already are. Nothing is moved into a mandated layout.
- Q: Must consumers that read files directly (bypassing the palace) use the corpus, or
  does mneme only report divergence? → A: **Required.** Every consumer of campaign files
  takes its file set from the mneme TOC. A consumer choosing its own files is
  non-compliant, not merely divergent.
- Q: Who defines the kinds? → A: Both. mneme defines a standard set of kinds that every
  campaign and every shared consumer uses by the same name; a campaign may also define
  its own kinds for material the standard set does not cover.
- Q: Is the corpus configuration its own file, or a section of `.mneme/mempalace.yaml`?
  → A: Its own YAML file. mempalace is one consumer of the corpus among several, so its
  authority is derived from the corpus configuration, not the home of it.
- Q: What default trust do the standard kinds carry? → A: NPC data, session summaries,
  party / PC data and grounding are `authoritative`; session prep is `reference`. A
  campaign may override any of them.
- Q: A file declared under two kinds can only be mined under one (mempalace's re-mine
  deletes a file's drawers in every wing). How is the mining kind chosen? → A: The GM
  marks it explicitly with `mined_as` on one of the declarations. The file is listed under
  both kinds in the TOC. No mark, or more than one, is invalid until the GM fixes it;
  mneme never picks.
- Q: Do the new owed rows (undeclared corpus, non-compliant consumers) make `mp status`
  fail? → A: Never. Owed work exits 0, like a pending recipe upgrade. Real corpus findings
  (undeclared drawers, unmined, stale, wrong-wing, missing, invalid) still fail.
- Q: What does mneme write for CampaignGenerator's search while CG still reads a single
  `canon_wing`? → A: Nothing transitional. CG learning `canon_wings` (and fixing every
  query that names old wings) is a prerequisite: no campaign gets a `corpus.yaml` until
  that CG change ships.
- Q: What protects formerly-authoritative material from an unnoticed prune? → A: `mp
  prune` refuses when its deletion set includes drawers from a wing that was
  `authoritative` before the corpus, naming the wing and file count, and proceeds only
  with `--include-former-canon <wing>`.
- Q: Can a declared file be a symlink (out-of-the-abyss's grounding docs are)? → A: Yes,
  if it resolves inside the campaign. mneme mines the real target. When a promotion
  re-points the symlink, the next `mp refresh` deletes the old target's drawers and mines
  the new one in the same step, with no prune or confirmation: the declared membership
  did not change, only its content.

## Overview

The GM works in sparse checkouts of each campaign, and that workspace fills with a large
volume of rough, generated, often contradictory text: drafts, extractions, staging
copies, reviews, backups. Out of that, the GM hand-curates a much smaller set of files
that are actually true, and they fall into a few **kinds**: NPC data, session summaries,
party / PC data, grounding documents, session prep.

Where each kind lives is **not fixed** and differs between campaigns. For example, on
disk today:

| Kind | obelisk | toee | out-of-the-abyss |
|---|---|---|---|
| NPC data | `docs/npcs/` (43) | `docs/npcs/` (empty) | `docs/npcs/` (96) |
| Session summaries | `docs/summaries/` (13) | none published yet | `docs/summaries/` (69) |
| Party / PC data | `docs/party.md` | `docs/party.md`, `docs/party/` | `docs/party.md`, `docs/party/`, per-PC backstory files |
| Grounding | four files in `docs/` | four files in `docs/` | four files in `docs/` |
| Session prep | `notes/` | `notes/sessions/` | `notes/` |

So the corpus is declared **by kind**: a per-campaign configuration names each kind and
gives either a directory or a list of files for it. The GM never has to move files into
a mandated layout. Every consumer asks for a kind ("the party files", "the summaries")
by name and receives the same list (Principle VII — reason in logical datasets, not
their backing paths).

Today a campaign's mempalace does not mine that curated set. It mines **whatever its
wings sweep in, minus a blocklist** (the recipe's baseline exclusions, the campaign's
`extra_exclusions`, and `.gitignore`), and the last wing is always the campaign root.
The palace therefore **fails open**: every new kind of generated output is mined until
someone notices and excludes it. Observed on disk (2026-10-22):

- **toee** — the root wing is trust `authoritative`, and nothing excludes
  `docs/campaign_state_draft.md`, `docs/party_draft.md` or
  `docs/party_draft.candidate.md`. Drafts are mined as canon.
- **obelisk** — the published `docs/npcs/` and `docs/summaries/` have no wing of their
  own; they are swept into the root wing at trust `reference`, alongside
  `docs/entity_registry.yaml.bak`, `docs/reviews/`, `docs/summary_native/` and
  `docs/archive/`. The wing named `summaries` points at the *rough* top-level
  `summaries/` pipeline output, not the published summaries.
- **out-of-the-abyss** — the sparse checkout has no mempalace authority at all, beside a
  `docs/` tree of 60+ entries of mixed published and working material.

There is a second failure behind the first. Several consumers answer questions about a
campaign: the mempalace MCP server Claude uses, CampaignGenerator's search, Claude skills
that read or index files directly (for example `/campaign-recall`, which searches session
summaries through its own zvec-grep index), and CampaignGenerator loads that read
`docs/*.md` from disk. mneme already makes the palace-backed consumers agree on **which
palace** to search (the faces, Principle V). Nothing makes any of them agree on **which
files**. Two consumers can give different answers to the same question because each is
reading a different set of documents — the split-brain this feature removes.

The decision this feature makes: **the corpus is declared, by kind, not discovered.**
For each kind, the GM names where its true files are; mneme mines exactly those,
publishes the resolved set — grouped by kind — so every consumer reads the same list, and
reports, never silently tolerates, any place the palace or a consumer disagrees with it.
Corpus membership is a precision decision; mneme never infers it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The palace contains exactly the curated files (Priority: P1)

The GM writes the campaign's corpus configuration: for each kind (NPC data, summaries,
party, grounding, prep) a directory or a list of files, wherever they happen to live in
that campaign. After a refresh, the palace holds drawers from those files and from
nothing else, however much rough material sits elsewhere in the checkout.

**Why this priority**: This is the reported problem. Until the palace stops failing open,
every search answer is contaminated by drafts and generated sprawl, and no downstream
agreement is possible.

**Independent Test**: In a campaign checkout containing both curated files and decoy
rough files (a `*_draft.md` beside a grounding doc, a new generated directory under
`docs/`), declare a corpus naming only the curated files, refresh, and verify every
drawer's source is a declared file and every declared file has drawers.

**Acceptance Scenarios**:

1. **Given** a corpus configuration declaring NPC data as `docs/npcs/`, summaries as
   `docs/summaries/` and grounding as a list of the four grounding files, **When** the GM
   refreshes, **Then** `docs/campaign_state_draft.md`, `docs/party_draft.md` and any
   other undeclared file produce no drawers.
2. **Given** two campaigns that keep party data in different places (one a single file,
   the other a directory plus loose files), **When** each declares its party kind with
   its own paths, **Then** both are mined as party data with no files moved.
3. **Given** a declared corpus, **When** a new generated directory appears under `docs/`
   and the GM refreshes, **Then** nothing from it is mined, with no exclusion added.
4. **Given** a kind declared as a directory such as `docs/npcs/`, **When** the GM adds a
   new NPC file to that directory and refreshes, **Then** the new file is mined — a
   declared directory admits its contents.
5. **Given** a declared corpus, **When** mneme renders the mining configuration, **Then**
   the rendered configuration contains no wing whose source is the campaign root and does
   not rely on a blocklist to keep undeclared material out.

---

### User Story 2 - Status proves the palace equals the corpus (Priority: P1)

The GM runs `mneme mp status` and learns, for each campaign, whether its palace matches
its declared corpus — and if not, exactly how it differs and which command fixes it.

**Why this priority**: Without verification, "the palace equals the corpus" is a claim,
not an observed fact (Principle I). Status is also the only way existing palaces — built
under the fail-open model — become visibly wrong instead of silently wrong.

**Independent Test**: Take a palace mined under the old wing model, declare a corpus for
it, and run status without refreshing. Verify it reports the undeclared sources it holds,
the declared files it is missing, and the remedy for each.

**Acceptance Scenarios**:

1. **Given** a palace holding drawers from files outside the declared corpus, **When** the
   GM runs status, **Then** status reports those as **undeclared** with their count, and
   names `mneme mp prune` as the remedy.
2. **Given** a declared file with no drawers, **When** the GM runs status, **Then** status
   reports it as **unmined** and names `mneme mp refresh` as the remedy.
3. **Given** a declared file whose content changed since it was mined, **When** the GM runs
   status, **Then** status reports it as **stale** and names `mneme mp refresh`.
4. **Given** a palace whose drawers match the declared corpus exactly and are current,
   **When** the GM runs status, **Then** the corpus dimension is reported ok — and only
   then.
5. **Given** status cannot determine a palace's drawer sources (store unreadable,
   mempalace unavailable), **When** the GM runs status, **Then** the corpus dimension is
   reported **unknown**, never ok.

---

### User Story 3 - Every consumer reads the same file list (Priority: P2)

A consumer that needs to know which files are true for a campaign — a Claude skill, a
CampaignGenerator load, an index builder — asks for a kind by name ("party", "summaries")
and reads one published list instead of choosing files or hardcoding paths for itself.

**Why this priority**: Making the palace exact (Stories 1–2) fixes every consumer that
searches through the palace. Consumers that bypass the palace still pick their own
files; this story gives them the same answer to consume.

**Independent Test**: Render the corpus for a campaign, then read the published list and
verify it names exactly the files the palace was mined from, with a content fingerprint
for each, and that re-rendering after a declaration change updates it.

**Acceptance Scenarios**:

1. **Given** a declared corpus, **When** mneme renders the campaign, **Then** it writes a
   corpus TOC listing, grouped by kind, every resolved file (declared files plus the
   contents of declared directories) with a content fingerprint and the trust level it
   was declared at.
2. **Given** the TOC, **When** a consumer asks for one kind (e.g. party), **Then** it
   receives exactly that kind's files, without knowing where that campaign keeps them.
3. **Given** the GM changes the declaration, **When** mneme renders, **Then** the TOC
   is regenerated; a TOC that no longer matches its declaration is reported stale by
   status.
4. **Given** a consumer reads the TOC, **When** it compares a file's current content
   to the recorded fingerprint, **Then** it can tell whether the file changed since the
   corpus was resolved.
5. **Given** a consumer that reads campaign files directly, **When** it acts on a
   campaign, **Then** it takes its file set from the TOC — for the kinds it needs —
   and does not choose, glob or hardcode files of its own.
6. **Given** a consumer that reads files directly, **When** the TOC is missing, stale
   or reports the corpus invalid, **Then** the consumer refuses to act and names the
   problem, rather than falling back to files of its own choosing.

---

### User Story 4 - Existing campaigns move to a declared corpus deliberately (Priority: P2)

A campaign whose authority still uses the wing-plus-blocklist model (every campaign
today) is shown as owing a corpus declaration. mneme can show the GM what the current
model actually mines, as input to the GM's decision, but never writes a corpus on the
GM's behalf.

**Why this priority**: Every existing campaign is in the old model. Converting them
silently would be mneme deciding corpus membership — the precision decision this feature
reserves for the GM.

**Independent Test**: On a campaign with no corpus declaration, run status and verify it
reports the corpus as undeclared (owed work), and that the inventory of what the current
model mines is presented as a proposal the GM edits, not applied.

**Acceptance Scenarios**:

1. **Given** a campaign authority with no corpus declaration, **When** the GM runs status,
   **Then** the corpus dimension reports **undeclared** as owed work, not as an error that
   blocks other dimensions.
2. **Given** an undeclared campaign, **When** the GM asks mneme for the current mined
   file set, **Then** mneme lists the files the existing wing model resolves to, grouped
   by wing, and writes nothing to the authority.
3. **Given** the GM writes a corpus declaration, **When** mneme next renders, **Then** the
   old root wing and blocklist-based mining are replaced by mining from the declaration,
   and the change is visible in status as undeclared drawers to prune.

---

### User Story 5 - See which consumers are not yet on the TOC (Priority: P3)

The GM can see, per campaign, every known consumer of its files, which kinds each one
uses, and whether it is compliant (searches the palace, or reads the TOC) or
non-compliant (still chooses files of its own).

**Why this priority**: Every consumer is required to use the TOC (Clarifications,
2026-10-23), but converting CampaignGenerator and the skills happens in their own repos.
Until each one lands, the remaining split-brain must be discoverable, not remembered
(Principle IX).

**Independent Test**: Review the consumer inventory for one campaign and verify every
listed consumer is classified compliant or non-compliant, and that each non-compliant
one appears in status as owed work with the files it reads outside the TOC.

**Acceptance Scenarios**:

1. **Given** the consumer inventory, **When** the GM views it for a campaign, **Then** each
   consumer is listed with the kinds it uses and classified compliant or non-compliant.
2. **Given** a non-compliant consumer, **When** the GM runs status, **Then** it appears as
   owed work naming the consumer and the files it reads that the TOC does not list, or
   the TOC files it misses.

---

### Edge Cases

- **A declared path does not exist.** A declared file or directory missing from the
  checkout is reported, naming the path; mneme does not silently drop it from the
  corpus.
- **Sparse checkout.** A declared path can be absent because it is outside the sparse
  checkout on this host, not because it was deleted. mneme must not treat "not checked
  out here" as "removed from the corpus", and must not offer to prune drawers on that
  basis.
- **A declared file is gitignored.** mempalace skips gitignored files when mining, and
  `mp prune` treats drawers from gitignored sources as orphans. A gitignored declared
  path is a contradiction, reported as an error naming the path — never mined-then-pruned.
- **A declared path is a symlink.** mempalace refuses to open a file that is itself a
  symlink (`O_NOFOLLOW`), but follows symlinked directories. A declared symlink whose
  target resolves inside the campaign is allowed: mneme mines the resolved target and the
  TOC records both paths. A symlink resolving outside the campaign, or to something that
  is not a regular file, is invalid and reported, never left to show up as "unmined".
- **A symlink is re-pointed** (a grounding promotion moves `docs/grounding/current` to a
  new generation). On the next refresh the old target's drawers are deleted and the new
  target is mined, in one step. Until that refresh, status reports the file as stale.
- **Overlapping declarations.** A file reachable through two entries is mined once.
  Within one kind that is harmless. Across two kinds (e.g. `docs/party.md` declared as
  both party and grounding) the file belongs to both kinds in the TOC, but is mined under
  the one kind the GM marks with `mined_as`. No mark, more than one mark, or differing
  trust levels are each reported as invalid for the GM to resolve.
- **A kind is not declared.** A campaign that has no published summaries yet (toee) simply
  omits that kind; consumers asking for it get an explicit "not declared for this
  campaign", distinct from "declared but empty".
- **An unknown kind name.** Because campaigns can define their own kinds, a typo
  (`sumaries`) must not silently become a new campaign kind. A name that is neither a
  standard kind nor explicitly declared by the campaign as one of its own is reported.
- **A campaign kind shadows a standard kind.** A campaign kind with the same name as a
  standard kind is an error; the campaign uses the standard kind instead.
- **A standard kind gains a campaign's kind later.** If mneme later adds a standard kind
  that a campaign already defines under the same name, that collision is reported for
  the GM to reconcile, never merged silently.
- **Non-text files in a declared directory.** A PDF or archive inside a declared directory
  is handled the way mempalace handles it today and listed in the existing skipped-files
  report (GH #31); it is not silently treated as mined.
- **A declared file is renamed or moved.** The old path becomes a missing declaration and
  its drawers become undeclared; both are reported. mneme does not guess that the new
  file is the same document.
- **Hand-edited TOC.** The TOC is derived. If its contents do not match what the
  declaration resolves to, status reports it stale; it is regenerated, never trusted.
- **Empty corpus.** A declaration that resolves to zero files is reported as an error,
  not mined into an empty palace.
- **Embedder mismatch.** Mining a declared corpus goes through the existing
  embedding-dimension guard unchanged; a mismatch refuses the write as it does today.

## Requirements *(mandatory)*

### Functional Requirements

**Declaration**

- **FR-001**: Each campaign MUST have a corpus configuration that declares its corpus
  **by kind**. For each kind, the GM gives either a directory or a list of files (paths
  relative to the campaign root); a kind MAY combine both.
- **FR-001a**: The corpus configuration MUST be its own campaign-level YAML file in the
  campaign's `.mneme/` directory (e.g. `.mneme/corpus.yaml`), separate from the mempalace
  authority. It is the one authority for corpus membership; the mempalace authority's
  mining wings are derived from it and MUST NOT declare corpus membership of their own.
- **FR-002**: The configuration MUST NOT require files to be at any particular location.
  Two campaigns MAY declare the same kind with entirely different paths.
- **FR-003**: mneme MUST define a set of **standard kinds**, including at least: NPC data,
  session summaries, party / PC data, grounding documents, and session prep. Standard
  kind names are a shared vocabulary that shared consumers (CampaignGenerator, the
  skills) ask for by name, and mean the same thing in every campaign.
- **FR-003a**: A campaign MAY define its own **campaign kinds** in its corpus
  configuration. A campaign kind MUST be explicitly declared as campaign-defined, MUST
  NOT reuse a standard kind's name, and is otherwise treated like any other kind: mined,
  listed in the TOC, verified by status, and subject to the TOC compliance rule.
- **FR-004**: Each kind MUST carry the trust level its files are mined at. Standard kinds
  have a mneme-defined default that the campaign MAY override (NPC data, summaries, party
  and grounding: `authoritative`; prep: `reference`); a campaign kind MUST state its trust
  level, since there is no default to fall back on.
- **FR-004a**: A file declared under more than one kind MUST be listed under every one of
  them in the TOC and MUST be mined under exactly one, the kind whose declaration marks it
  `mined_as`. mneme MUST NOT choose the mining kind itself.
- **FR-005**: A file MUST be in the corpus if and only if it is named by, or lies under a
  directory named by, some declared kind. There MUST be no implicit inclusion of the
  campaign root.
- **FR-006**: mneme MUST NOT add, remove or change corpus entries on its own. Every change
  to corpus membership is made by the GM editing the configuration.

**Mining**

- **FR-007**: When a campaign has a corpus configuration, mneme MUST render mempalace's
  mining configuration from it such that only corpus files can produce drawers, without
  relying on a blocklist to keep other material out. Each drawer MUST record the kind it
  was mined as, so a search can be scoped to a kind.
- **FR-008**: The rendered mining configuration MUST NOT contain a wing whose source is
  the campaign root.
- **FR-009**: Existing protections MUST continue to apply to corpus mining: the
  embedding-dimension guard, the working-copy write isolation, and the skipped-files
  report.

**Table of contents (TOC)**

- **FR-010**: On render, mneme MUST write a derived corpus TOC for the campaign,
  listing every resolved corpus file grouped by kind, with a content fingerprint and its
  trust level.
- **FR-011**: The TOC MUST be marked as derived and do-not-edit, and MUST record
  which version of the configuration it was resolved from, so a stale TOC is
  detectable.
- **FR-012**: The TOC MUST be readable by any consumer without running mneme, and a
  consumer MUST be able to read one kind's files without reading the others.
- **FR-013**: The TOC MUST distinguish a kind that is declared but resolves to no
  files from a kind that is not declared for the campaign.

**Verification**

- **FR-014**: `mneme mp status` MUST report a corpus dimension per campaign, comparing the
  palace's drawer sources against the resolved corpus, broken down by kind.
- **FR-015**: The corpus dimension MUST distinguish, with counts and the files involved:
  **undeclared** (drawers from files outside the corpus), **unmined** (corpus files with
  no drawers), **stale** (corpus files changed since mined), **missing** (declared paths
  not present), **wrong-wing** (corpus files whose drawers sit outside their mining kind),
  and **invalid** (gitignored, symlinks resolving outside the campaign, unknown-kind or
  conflicting declarations). A re-pointed symlink counts as stale.
- **FR-016**: Each non-ok corpus finding MUST name its remedy: `mp prune` for undeclared,
  `mp refresh` for unmined and stale, a configuration edit for missing and invalid.
- **FR-017**: The corpus dimension MUST be ok only when the palace's drawer sources equal
  the resolved corpus and every drawer is current. Anything mneme cannot verify MUST be
  reported unknown, never ok.
- **FR-018**: `mneme mp prune` MUST treat drawers from undeclared files as prunable,
  under its existing preview / `--confirm --expect N` / backup protocol, and MUST NOT
  prune drawers whose declared source is merely absent from this host's sparse checkout.

**Migration**

- **FR-019**: A campaign with no corpus configuration MUST be reported as owing one,
  without blocking its other status dimensions or its existing mining.
- **FR-020**: mneme MUST be able to list, for a campaign with no corpus configuration,
  the files its current wing model resolves to, as read-only input to the GM's
  configuration. It MUST NOT write a corpus configuration on the GM's behalf.

**Consumers**

- **FR-021**: Every consumer of campaign files MUST take its file set from the mneme
  TOC. The palace is itself a TOC consumer: mining reads the TOC (FR-007), so consumers
  that search through the palace are compliant by construction. A consumer that reads
  files directly MUST read them from the TOC, by kind.
- **FR-022**: A consumer that reads files directly MUST refuse to act when the TOC is
  missing, stale, or reports the corpus invalid, and MUST NOT fall back to choosing files
  itself.
- **FR-023**: mneme MUST maintain an inventory of the known consumers of each campaign's
  files, recording which kinds each uses and classifying each as compliant
  (palace-backed or TOC-backed) or non-compliant (chooses its own files).
- **FR-024**: `mneme mp status` MUST surface every non-compliant consumer as owed work,
  naming the consumer and the files it reads outside the TOC.

### Key Entities

- **Corpus configuration**: The GM-authored, per-campaign declaration of the corpus by
  kind. The one place corpus membership is decided (Principle V).
- **Kind**: A named category of true campaign material that consumers ask for by name.
  Either a **standard kind** (defined by mneme, same meaning in every campaign: NPC data,
  session summaries, party / PC data, grounding, session prep — each with a default
  trust level) or a **campaign kind** (defined by one campaign, with an explicit trust
  level).
- **Kind declaration**: One kind's entry in a campaign's configuration — a directory, a
  list of files, or both — plus an optional trust override.
- **Resolved corpus**: The concrete set of files the configuration names on this
  checkout, grouped by kind — declared files plus the contents of declared directories.
- **Corpus TOC**: The derived, do-not-edit record of the resolved corpus, with a
  content fingerprint per file and the declaration version it came from. A cache of the
  declaration, never a second authority.
- **Corpus finding**: One status result for a campaign's corpus dimension — undeclared,
  unmined, stale, missing, invalid, unknown or ok — with the files involved and its
  remedy.
- **Consumer**: Anything that answers questions about a campaign from its files (the
  mempalace MCP server, CampaignGenerator search and loads, Claude skills, external
  indexes), classified by where it takes its file set from.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After declaring a corpus and refreshing, 100% of a campaign's drawers come
  from declared files, verified by status and independently by listing drawer sources.
- **SC-002**: Adding any number of new files outside the declared entries and refreshing
  produces zero new drawers.
- **SC-003**: For each of the three existing campaigns (obelisk, toee, out-of-the-abyss),
  status on the current palace identifies every undeclared source — including toee's
  draft grounding files — before the GM runs any prune.
- **SC-004**: A corpus finding never reports ok when the palace and corpus differ, across
  a test matrix covering each finding type (undeclared, unmined, stale, missing, invalid,
  unknown).
- **SC-005**: The GM can answer "which files is this campaign's palace built from?" from
  one place, without reading wing configs, exclusion lists or `.gitignore`.
- **SC-007**: All three existing campaigns can be configured with their files where they
  are today — zero files moved or renamed to satisfy the configuration.
- **SC-008**: Two consumers asking for the same kind of the same campaign receive
  identical file lists, in every case tested.
- **SC-006**: Every known consumer of each campaign appears in the consumer inventory with
  a classification; none is unclassified.
- **SC-009**: Once the consumer follow-ups land, zero known consumers are non-compliant:
  none globs, hardcodes or otherwise chooses campaign files outside the TOC.

## Assumptions

- The standard kinds are defined by mneme in the recipe and versioned with it; adding a
  standard kind is a recipe change that campaigns adopt through the existing publish /
  adopt flow.
- Shared consumers ask only for standard kinds; a campaign kind is used by consumers
  specific to that campaign (its own skills, its notes) but still flows through the
  palace and the TOC like any other kind.
- The curated material lives in the sparse campaign checkout. `~/src/campaigns-public` is
  a downstream publication target, not a corpus source.
- A declared directory admits all of its contents, recursively. Finer filtering inside a
  declared directory is out of scope; the GM lists files instead.
- The TOC is derived per host from the tracked declaration and the checked-out
  files. Whether it is committed to git is a planning decision, constrained by feature
  006's rule that anything tracked must be true on every host.
- The existing wing model keeps working for campaigns that have not declared a corpus;
  removing it is a later step once every campaign has a declaration.
- The recipe (`mneme/recipes/`) gains a corpus-based scaffold; whether that is a new
  recipe version is a planning decision.
- Bringing direct-reading consumers onto the TOC requires changes in those consumers'
  own repos (CampaignGenerator, the skills, the zvec-grep index behind
  `/campaign-recall`). This feature defines the TOC, the compliance rule and the
  inventory; each consumer's conversion is a tracked follow-up, and until it lands that
  consumer is shown as non-compliant owed work.
- mempalace's current behaviour holds: its scanner skips symlinks
  (`Mempalace/mempalace/miner.py`, the symlink skip in `scan_project`), its reader opens
  files with `O_NOFOLLOW` (`_read_text_no_follow`), and it honours `.gitignore` itself
  when mining.
