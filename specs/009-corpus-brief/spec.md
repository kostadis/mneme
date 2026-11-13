# Feature Specification: Corpus Brief

**Feature Branch**: `corpus-brief`

**Created**: 2026-11-13

**Status**: Draft

**Input**: User description: "Corpus brief: a GM-declared load-now set plus the full corpus TOC as a map, so briefing consumers (first: the campaign-prep skill, mytools#87) know which declared files to read up front and where everything else is, without hardcoding paths or loading a whole kind. Declared as a top-level `brief:` list of exact file paths in .mneme/corpus.yaml; every entry must be a file of some declared kind (the brief is a subset of the corpus, never a second list); no `brief:` means briefing consumers refuse rather than guess. Exposed as `mneme corpus brief CAMPAIGN [--json]` and an MCP tool `corpus_brief` on the existing server, returning paths + byte sizes (not contents) for the brief and the whole TOC, resolved fresh on every call. Refuses on an invalid/undeclared corpus, missing brief, or brief files not present on this checkout. Campaigns with no corpus are refused, no exceptions (GM ruling). Consumers must run against the workspace mneme owns (--dir + store-alias guard rejects stale copies). Motivation: OOTA's grounding kind is ~786 KB (~200K tokens) vs ~345 KB for the four core docs. A WIP spike exists on branch corpus-brief (commit 739851f) and should be treated as exploratory input, not as the design."

## Context

Feature 007 made `.mneme/corpus.yaml` the single declaration of a campaign's curated files,
grouped by kind, and obliged every consumer to take its files from mneme instead of globbing
or hardcoding paths (mytools#87). That contract answers "which files are kind K?", but a
*briefing* consumer, such as the `campaign-prep` skill that loads a campaign's state before
session prep, needs a different answer: "which few files do I read now, and where is
everything else if I need it later?"

The corpus has three roles, and only one of them is meant to be loaded (GM, 2026-11-13):

- **Planning** (`docs/planning.md`) is what the corpus *produces*: the working document
  session prep starts from. It is the thing a briefing consumer loads as context.
- **Grounding** (`world_state`, `campaign_state`, `party`, `docs/reference/*`, timelines) is
  a navigation index over the evidence. It is searched, not loaded.
- **Evidence** (summaries, NPC dossiers, arcs, …) is the authority. It is searched, and a
  claim is confirmed by reading the cited source.

Reading a whole kind is therefore the wrong answer. Out of the Abyss declares 15 files as
`grounding`, about 786 KB (≈200K tokens), while its planning document is about 43 KB
(≈11K tokens). Picking planning out inside the skill would put a hardcoded path back into a
consumer, which is exactly what 007 removed. Which files are loaded up front is the GM's
editorial decision about the campaign. It belongs in the campaign's own declaration, next to
the corpus it is drawn from, as a general `brief:` list rather than a special "planning"
concept (GM decision 2026-11-13). Today the GM's brief is expected to be the planning
document alone; the list form leaves room to change that without a new feature.

## Clarifications

### Session 2026-11-13

- Q: Does "searchable" in the map mean declared-to-be-mined or actually present in the palace now? → A: Declared. The map reports what the corpus declares as mined; palace freshness stays `mneme mp status`'s job, and the brief never queries the palace.
- Q: How detailed is the map of the rest of the corpus? → A: A per-kind summary (trust, searchable, file count, total bytes). Per-file lists stay one call away via the existing per-kind file list (`mneme corpus toc --kind K`).
- Scope addition (GM request, 2026-11-13): a GM-run migration that adds `brief:` to an
  existing `corpus.yaml`, preview by default, written only on explicit apply (User Story 5,
  FR-016–FR-020). FR-004 is narrowed accordingly.
- Q: Should `mneme mp status` list a campaign with a valid corpus but no `brief:` as outstanding work? → A: No. `mneme corpus check` reports "brief: not declared" and briefing consumers refuse with a fix-it message; status stays quiet, since not every campaign needs a brief.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A briefing consumer loads exactly the GM's load-now set (Priority: P1)

The GM runs `campaign-prep` in a campaign workspace. The skill asks mneme for the campaign's
brief, reads the files mneme names (today, the planning document) and no others, and keeps a
map of the rest of the corpus: which kinds exist, how far each is trusted, and which can be
searched. When a prep question needs more, it searches rather than loading grounding
documents wholesale.

**Why this priority**: This is the reason for the feature. Without it, `campaign-prep`
cannot be migrated to the declared corpus (mytools#87) without either loading ~200K tokens of
documents meant to be searched, or reintroducing a hardcoded path.

**Independent Test**: Declare a `brief:` naming only the planning document in a campaign
with a larger `grounding` kind, ask for the brief, and confirm it names exactly that file
(with its size) plus a map of every declared kind: its trust, whether it is searchable, its
file count and its total size.

**Acceptance Scenarios**:

1. **Given** a valid corpus whose `brief:` lists files, **When** a consumer asks for the
   brief, **Then** it receives those files in the declared order, each with its size and
   the kind(s) it belongs to, plus every declared kind with its trust level, whether its files
   are searchable in the campaign's palace, its file count and its total size. No per-file
   listing of the other kinds is included.
2. **Given** the same campaign, **When** a file is added to a folder declared under some
   kind, **Then** the next brief request counts it in that kind's file count and total size
   without any render or regeneration step, and the brief itself is unchanged.
3. **Given** a consumer that asks through the command line and one that asks through the
   assistant tool interface, **When** both ask about the same campaign, **Then** they receive
   the same answer.

---

### User Story 2 - The GM declares and checks the brief (Priority: P1)

The GM adds a `brief:` list to `.mneme/corpus.yaml` and runs the existing corpus check. The
check confirms the brief is part of the corpus, or names each entry that is not.

**Why this priority**: The brief is only safe if it can never become a second, drifting list
of paths. Validation at declaration time is what keeps it a subset of the corpus.

**Independent Test**: Add a `brief:` naming one declared file and one undeclared file; the
check fails and names the undeclared one. Remove it; the check passes and reports the
brief's size.

**Acceptance Scenarios**:

1. **Given** a `brief:` entry that is not a file of any declared kind, **When** the GM checks
   the corpus, **Then** the corpus is invalid, and the finding names that path and says it
   must be declared under a kind first.
2. **Given** a `brief:` naming a folder, a pattern, a path outside the campaign, or the same
   file twice, **When** the GM checks the corpus, **Then** each is reported as a finding.
3. **Given** a valid corpus, **When** the GM checks it, **Then** the output says whether a
   brief is declared and, if so, how many files and how many bytes it holds.

---

### User Story 3 - Consumers refuse instead of guessing (Priority: P1)

Whenever mneme cannot give a trustworthy brief, the consumer stops and shows the GM mneme's
reason. It never falls back to globbing, a remembered path list, or a whole kind.

**Why this priority**: A silent fallback is how the hardcoded lists survived before 007. The
GM's ruling is that a campaign with no declared corpus is refused, with no exceptions.

**Independent Test**: Ask for the brief in (a) a campaign with no `corpus.yaml`, (b) a
campaign with a corpus but no `brief:`, (c) a stale second checkout of a registered
campaign, and (d) a sparse checkout missing a brief file. Each request fails with a distinct,
actionable reason and returns no file list.

**Acceptance Scenarios**:

1. **Given** a campaign with no declared corpus, **When** the brief is requested, **Then**
   mneme refuses with "declares no corpus" and returns no files.
2. **Given** a valid corpus with no `brief:`, **When** the brief is requested, **Then** mneme
   refuses with a reason saying no brief is declared and how to declare one. The map alone is
   not returned as a substitute.
3. **Given** an invalid corpus (any 007 finding), **When** the brief is requested, **Then**
   mneme refuses with the same findings the corpus check reports.
4. **Given** a brief file that is declared but not present on this checkout (not
   materialized in a sparse checkout, or missing), **When** the brief is requested, **Then**
   mneme refuses and names each absent file. It does not return a partial brief.
5. **Given** a directory that is a second or stale copy of a campaign mneme owns elsewhere,
   **When** the brief is requested for that directory, **Then** mneme refuses (the existing
   ownership and store-alias guards) rather than describing the other copy's files.

---

### User Story 4 - Consumers and the GM can see who uses the brief (Priority: P3)

The consumer inventory (007 `consumers.yaml`) can record that a consumer reads its files
through the brief, so `mneme corpus consumers` reports it as compliant, and the consumer
obligations documentation tells skill authors when to use the brief instead of a kind.

**Why this priority**: Needed to finish mytools#87 for `campaign-prep`, but the brief works
without it.

**Independent Test**: Mark a consumer row as reading through the brief and confirm the
consumers report lists it as compliant.

**Acceptance Scenarios**:

1. **Given** a consumer row that declares it reads through the brief, **When** the GM lists
   consumers, **Then** that row is reported as compliant.
2. **Given** the consumer obligations documentation, **When** a skill author reads it,
   **Then** it states when to use the brief, the per-kind file list, or the palace, and that
   every refusal must be shown to the GM rather than worked around.

---

### User Story 5 - The GM migrates existing corpora to declare a brief (Priority: P2)

The four campaigns already have a `corpus.yaml` with no `brief:`. The GM runs a migration
per campaign (or for all of them) that shows exactly the `brief:` block it would add and the
size of that brief, and then writes it only when the GM applies it. The default proposal is
the planning document; the GM can name other files.

**Why this priority**: Without a brief, every briefing consumer refuses (FR-010). Hand-editing
four YAML files is error-prone, and an edit that breaks `corpus.yaml` breaks every 007
consumer at once.

**Independent Test**: Run the migration on a campaign without a brief: the preview shows the
block and writes nothing. Run it with apply: `corpus.yaml` gains exactly that block, every
other byte is unchanged, and `mneme corpus check` reports the brief. Run it again: it refuses
because a brief exists.

**Acceptance Scenarios**:

1. **Given** a valid corpus without `brief:`, **When** the GM runs the migration without
   apply, **Then** it prints the block it would append, each proposed file with its kinds and
   size, and the total size, and the file on disk is unchanged.
2. **Given** the same campaign, **When** the GM runs it with apply, **Then** `corpus.yaml`
   gains exactly the previewed block, every other byte (comments and order included) is
   unchanged, and the result passes the corpus check.
3. **Given** a proposed file that is not a declared corpus file, **When** the GM runs the
   migration (preview or apply), **Then** it refuses, names the file, and writes nothing.
4. **Given** a corpus that already declares `brief:`, or one that is invalid, or a campaign
   with no corpus, **When** the GM runs the migration, **Then** it refuses and writes nothing.
5. **Given** several campaigns, **When** the GM runs the migration for all of them, **Then**
   each campaign is previewed or applied independently, and one campaign's refusal does not
   stop or roll back another's.

---

### Edge Cases

- A brief file is declared under two kinds: it appears once in the brief, listing every kind
  it belongs to.
- A brief file is reachable through a symlink: it appears under its declared path, the one
  the consumer opens, as the per-kind file list already does.
- A brief entry names a file that a declared folder would contain but that git ignores: this
  is not in the corpus, so the brief is invalid (the entry names a non-corpus file).
- A `brief:` that is present but empty: a finding (declare files, or omit the key).
- A brief file is very large: mneme reports its size and does not truncate or refuse. The
  consumer decides how to read it.
- The corpus is large (hundreds of files): the map stays one entry per kind, so its size
  depends on the number of kinds, not files. A consumer that needs a kind's files asks for
  that kind's file list.
- A campaign's `corpus.yaml` changes between two requests: each answer reflects the
  declaration and disk at the time of that request, and carries the declaration's fingerprint
  so two answers can be compared.

## Requirements *(mandatory)*

### Functional Requirements

**Declaration**

- **FR-001**: A campaign's `.mneme/corpus.yaml` MUST accept an optional top-level `brief:`
  that lists exact file paths, relative to the campaign root, in the order the GM wants
  them read.
- **FR-002**: Every `brief:` entry MUST be a file that the corpus declares under some kind.
  An entry that is not MUST make the corpus invalid, with a finding naming the path. The brief
  is never a second, independent list of paths.
- **FR-003**: `brief:` entries MUST follow the same path rules as the rest of `corpus.yaml`:
  relative, POSIX, no escape from the campaign root. Folders, patterns, duplicates and an
  empty list MUST each be findings.
- **FR-004**: mneme MUST NOT write or modify `brief:` on its own initiative. Only the GM
  declares it, by hand or through the GM-run migration (FR-016–FR-020), which writes only what
  the GM approved in its preview. A skeleton written by `mneme corpus init` MAY show it as a
  commented example. Every other mneme edit of `corpus.yaml` (e.g. the adopt-time kind move)
  MUST leave `brief:` byte-for-byte unchanged.

**Answer**

- **FR-005**: mneme MUST provide a brief answer for a campaign that contains (a) the brief's
  files in declared order, each with its declared path, size in bytes, the kind or kinds it
  belongs to, and its trust level; (b) every declared kind with its trust level, whether the
  corpus declares its files to be mined into the campaign's palace (and so meant to be reached
  by search), its file count and its total size in bytes, and no per-file listing; (c) the total size of the brief; and (d) the campaign name and the
  declaration's fingerprint.
- **FR-006**: The brief answer MUST be resolved from the declaration and the disk at the time
  of each request. It MUST NOT read the TOC snapshot or any other cached copy.
- **FR-007**: The brief answer MUST carry paths and sizes only, never file contents.
- **FR-007a**: Producing the brief answer MUST NOT query the palace. "Searchable" means
  declared to be mined; whether the palace is built and fresh is reported by `mneme mp status`,
  and a brief MUST succeed while the palace is unreadable.
- **FR-008**: The brief answer MUST be available both from the command line
  (`mneme corpus brief CAMPAIGN`, human-readable and `--json`) and as a tool on mneme's
  existing assistant tool server (`corpus_brief`). The two MUST be produced by one shared
  code path so they cannot disagree.
- **FR-009**: The command-line form MUST accept an explicit workspace directory, with the
  same ownership and store-alias checks as every other `mneme corpus` command.

**Refusal**

- **FR-010**: mneme MUST refuse, returning no file list, when the campaign declares no
  corpus; when the corpus is invalid; when no `brief:` is declared; or when any brief file is
  declared but absent on this checkout. Each refusal MUST carry a distinct, stable reason
  code and a human-readable detail naming what to fix.
- **FR-011**: A missing brief MUST NOT be treated as an empty brief, and a refusal MUST NOT
  be accompanied by a substitute answer, such as the map alone or a whole kind.
- **FR-012**: The command-line form MUST exit non-zero on every refusal and print the reason
  on the error stream.

**Visibility**

- **FR-013**: The existing corpus check MUST report whether a brief is declared and, when it
  is, its file count and total size.
- **FR-013a**: A missing brief MUST NOT be reported as outstanding work by `mneme mp status`
  or make a campaign non-conformant. Only `mneme corpus check` and the refusing consumer
  surface it.
- **FR-014**: The consumer inventory MUST be able to record that a consumer reads through the
  brief, and the consumers report MUST count such a consumer as compliant.
- **FR-015**: The consumer obligations documentation MUST describe the brief: when a consumer
  uses it, what it returns, that the rest of the corpus (grounding included) is reached by
  search rather than loaded, and that every refusal is shown to the GM, never worked around.

**Migration**

- **FR-016**: mneme MUST provide a GM-run migration that adds a `brief:` to an existing
  `corpus.yaml`, for one named campaign or for every campaign mneme owns.
- **FR-017**: The migration MUST preview by default: print the exact block it would add and
  each proposed file's kinds and size, and write nothing. It MUST write only when the GM
  passes an explicit apply flag.
- **FR-018**: The proposed brief MUST default to `docs/planning.md` and MUST accept the GM's
  own list of files instead, in the GM's order. Every proposed file MUST already be a
  declared corpus file present on this checkout, or the migration refuses for that campaign.
- **FR-019**: Applying MUST append the `brief:` block and change no other byte of
  `corpus.yaml`. The resulting bytes MUST pass the same validation as `mneme corpus check`
  before they replace the file, and the replacement MUST be atomic.
- **FR-020**: The migration MUST refuse, writing nothing, for a campaign with no corpus, an
  invalid corpus, or a corpus that already declares `brief:` (in any form). It never edits
  or replaces an existing brief. Across several campaigns, each one succeeds or refuses on
  its own, and the run's exit status reports whether any refused.

### Key Entities

- **Brief**: The GM's ordered load-now selection of corpus files for a campaign. It belongs
  to the campaign's corpus declaration, is a subset of the declared files, and has no
  existence apart from that declaration.
- **Brief answer**: What a consumer receives: the brief entries (path, size, kinds, trust),
  the corpus map (every kind: trust, searchable, file count, total size), the brief's total size,
  and the campaign plus declaration fingerprint. It is derived on each request and never
  stored.
- **Briefing consumer**: A skill or tool that loads a campaign's context up front (first:
  `campaign-prep`). It reads only the brief's files at start, reaches everything else by
  searching the palace (using the map to know what is searchable and how far to trust it),
  reads a cited source to confirm a claim, and refuses when mneme refuses.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For Out of the Abyss, with a brief of the planning document alone, a briefing
  consumer loads ≈43 KB up front (against ≈786 KB for the whole `grounding` kind and ≈345 KB
  for the four documents the old skill hardcoded), with no path written into the consumer.
- **SC-002**: Every file named in a brief answer is a file the corpus check also reports as
  declared: 0 brief entries outside the corpus across all declared campaigns.
- **SC-003**: Each of the four refusal cases (no corpus, invalid corpus, no brief, absent
  brief file) and the stale-copy case produces a refusal with no file list, verified per case.
- **SC-004**: The command-line and assistant-tool answers for the same campaign are identical
  in content for every campaign with a declared brief.
- **SC-005**: A file added to a declared folder is counted in the next brief answer's map with
  no intermediate command run.
- **SC-007**: The brief answer's size grows with the number of declared kinds and brief files,
  not with the number of corpus files: for Out of the Abyss (~470 declared files) the answer
  stays under a few kilobytes.
- **SC-006**: All four campaigns covered by mytools#87 (obelisk, toee, out-of-the-abyss,
  Phandalin) can be migrated to a brief with one previewed, then applied, migration run each,
  and each passes the corpus check afterwards with every pre-existing byte of its
  `corpus.yaml` unchanged.

## Assumptions

- The four registered campaigns already have valid 007 corpora (verified 2026-11-13). This
  feature ships the migration; running it on each campaign and committing the result in the
  campaigns repo is GM work after it ships.
- One brief per campaign is enough for now. Named briefs for different consumers (prep versus
  consistency checking) are out of scope; a single top-level list was chosen over per-file
  flags and named profiles (GM decision 2026-11-13).
- The planning document stays an ordinary member of the corpus: declared under a kind, mined,
  and searchable like any other file. Treating it as a product kept out of search was
  considered and not chosen (GM decision 2026-11-13). Search results already carry each
  file's kind and trust, so planning's own claims are distinguishable from evidence.
- mneme reports sizes but sets no size budget. Deciding how much to read stays with the
  consumer.
- Migrating `campaign-prep` and the other mytools skills to the brief is consumer work
  tracked in mytools#87, not part of this feature. This feature delivers the declaration, the
  answer, the refusals and the consumer contract.
- Shrinking oversized grounding documents (e.g. the 122 KB audit section inside Out of the
  Abyss's `campaign_state.md`) is a CampaignGenerator concern, outside this feature.
- The WIP spike on branch `corpus-brief` (commit 739851f) is exploratory input. Nothing in it
  is presumed to survive into the plan.
