# Implementation Plan: Declared Campaign Corpus

**Branch**: `007-declared-campaign-corpus` | **Date**: 2026-10-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/007-declared-campaign-corpus/spec.md`

## Summary

A campaign's palace today mines whatever its wings sweep in, minus a blocklist, with a root
wing on `.` (`render.py:81-92`, recipe v2 scaffold). It fails open. toee mines its draft
grounding docs as canon, and obelisk's published NPCs and summaries are swept into the root
wing beside backups and reviews. Separately, around 50 consumers pick campaign files for
themselves, and only four go through the palace (research R9).

This feature makes the corpus **declared, by kind**. `.mneme/corpus.yaml` is the GM's one
authority (FR-001a). It maps each kind to a directory or a list of files. The standard kinds
come from the recipe; campaign kinds are declared explicitly. mneme resolves the declaration
into a host-local TOC (`.mneme/corpus.toc.json`) that every consumer must read (FR-021). It
mines each kind as its own wing from an exact file list, and status compares three sets to
prove the palace equals the TOC.

Technical approach, set by what mempalace actually does:

- **Mining by explicit list, not by ignore rules.** `miner.mine()` already accepts
  `files=` (`miner.py:2362`), but the CLI does not expose it. mneme drives mempalace only by
  subprocess, so mempalace gains `mine --files-from`. Per-kind `--wing <kind>` mines make
  the kind the drawer's wing (R1). An allowlist `.mempalaceignore` was traced and rejected:
  one ignore file and one wing per mine cannot separate kinds that share `docs/`.
- **One file, one mining kind.** A re-mine deletes a file's drawers across every wing
  (`miner.py:2078`), so a file in two kinds is listed under both in the TOC but mined under
  one. The GM names which, with `mined_as`; mneme never picks (R2).
- **Status from three sets.** These are the TOC, `mempalace sources --json` (new; read-only)
  and a mneme-written `mneme-corpus-mined.json` holding sha256 at mine time. mempalace keeps
  only mtime, and mtime is not a content fact (R3).
- **Prune by exact set.** `sync --apply` cannot delete drawers from files that exist but are
  undeclared. mneme computes `undeclared ∪ (missing − not_materialized)` itself and deletes
  through a new `mempalace forget --sources-from`, under the existing preview / `--expect N` /
  backup / re-verify protocol (R4). Sparse-absent files are never pruned (R7).

The wing model keeps working, unchanged, for campaigns without `corpus.yaml` (FR-019).

## Technical Context

**Language/Version**: Python 3.11+ (existing `hypostasis` + `mneme` packages)

**Primary Dependencies**: PyYAML, Typer, stdlib `hashlib`/`json`/`subprocess`. mempalace is
used via its CLI only. No new runtime dependency.

**Storage**: Files only. `.mneme/corpus.yaml` (tracked authority). `.mneme/corpus.toc.json`
(derived, host-local, gitignored). `<store>/mneme-corpus-mined.json` (derived, store
lifecycle). `mneme/recipes/mempalace.recipe.v3.yaml` and `mneme/recipes/consumers.yaml`
(mneme-owned).

**Testing**: pytest (`tests/unit`, `tests/integration`). `tests/fixtures/stub_mempalace.py`
is extended with `mine --files-from`, `sources --json` and `forget`. The real-binary lane is
`tests/integration/test_real_mempalace_e2e.py` (`MNEME_REAL_MEMPALACE_VENV`). ruff clean.
Never run pytest inside `git rebase --exec` (memory: tests inherit `GIT_DIR`).

**Target Platform**: Linux/WSL CLI, two hosts, sparse campaign checkouts.

**Project Type**: Single project — CLI + library. There is a cross-repo dependency on
mempalace, plus follow-ups in CampaignGenerator and the skills.

**Performance Goals**: Resolving the TOC hashes every corpus file. That is hundreds of small
markdown files per campaign, well under a second. `sources --json` is one store scan per
status run.

**Constraints**:
- mneme never infers corpus membership or a file's mining kind (FR-006, R2).
- Unknown is never OK (FR-017).
- Nothing tracked carries host-local values (006). That is why the TOC is gitignored.
- Prune never deletes sparse-absent sources (FR-018).
- Campaigns without `corpus.yaml` behave exactly as today.

**Scale/Scope**: Three managed campaigns (obelisk, toee, out-of-the-abyss; the last has no
authority yet). Five standard kinds. Roughly 50 consumers inventoried, about 46 of them
non-compliant at the start.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Silicon Truth** ✅ — The corpus row is computed from observed drawer sources
  (`sources`) and observed content hashes, never from "the render succeeded". Unreadable
  means `UNKNOWN` (FR-017). Staleness uses sha256, not mtime, which a checkout rewrites (R3).
  Prune re-verifies after applying (R4). *Kills the Optimistic Lie* of today's index row,
  which says `BUILT` while it cannot see undeclared, unmined or changed files
  (`conform.py:234-236`).
- **II. Sovereign Identity** ✅ — Kinds are meanings ("the party files"). Paths are each
  campaign's current encoding, injected from its own configuration (FR-002). No consumer
  hardcodes a location once converted.
- **III. Intrinsic State** ✅ — The corpus declaration travels inside the campaign. The TOC
  and the mined record are regenerable caches, so losing them loses nothing.
- **IV. Transient Viewer / Brick Test** ✅ — Delete the TOC and the mined record:
  `mp render` + `mp refresh` rebuild both from `corpus.yaml` and the files. mneme holds no
  irreplaceable state.
- **V. One Authority, No Split-Brain** ✅ *with two named transitions* — `corpus.yaml` is the
  one place membership is decided. The mempalace authority's `wings:`/`extra_exclusions:`
  are forbidden beside it (`dual-authority`, R8). Every other copy (TOC, root
  `mempalace.yaml`, CG search face) is derived and stamped. The two existing second
  authorities, **CG `documents[]`** and **CG `grounding_bundle.py`'s hardcoded names**, are not
  introduced by this feature. They are surfaced as non-compliant consumers, and their
  conversion removes them (R9). The transitional `canon_wing` written beside `canon_wings`
  (R8) is derived, not authoritative.
- **VI. Federated, input[∞]** ✅ — Per-campaign, per-kind mining. One invalid campaign or
  failed kind is one finding, not a wedged fleet run.
- **VII. Logical Datasets** ✅ — This feature is Principle VII applied to campaign content.
  Consumers ask for a dataset by name and the TOC is the only encoding. mempalace is still
  driven by its CLI, never imported.
- **VIII. Transform the Constraint** ✅ — The hard problem is "make an ignore-rule engine
  express an allowlist, per kind, consistently with sync". It is deleted by passing the list
  directly, which the Python API already supports. The cost is three small mempalace CLI
  verbs over existing internals. The negation-ignore approach was traced and rejected as
  the more complex path (R1).
- **IX. Observability** ✅ — Undeclared campaigns, every corpus finding with its remedy, and
  the non-compliant consumer count all appear in `mp status`. `mneme corpus current` makes
  today's actual corpus discoverable before the GM writes the declaration.

**Human checkpoint (Authority & the Human Checkpoint)**: four inputs are precision decisions
that the GM ratifies. None feeds implementation unreviewed.
1. The per-kind default trust levels (R6). **Ratified 2026-10-23.**
2. The `mined_as` rule for files shared across kinds (R2). **Ratified 2026-10-23.**
3. The seeded consumer inventory, which is model output from a read-only sweep (R9).
   **Reviewed 2026-10-23**: written to `mneme/recipes/consumers.yaml` from the GM's marks
   only — 52 consumers (49 independent, 2 palace, 1 partial); 3 dropped as not consumers.
4. Each campaign's `corpus.yaml`. The GM writes these; mneme only offers `corpus current`
   and a pathless skeleton.

**Result: PASS.** No violations. Complexity Tracking is empty.

### Post-design re-check (after Phase 1)

**Still PASS.** Three design choices were re-checked because each could have introduced a
violation:
- **The mined record** (`mneme-corpus-mined.json`) could look like a second database of
  palace content (V). It is not: it records only what mneme fed to mempalace, it is
  regenerated by every mine, and `regenerate` wipes it with the store. It is the same class
  of artifact as GH #31's `mneme-last-mine.json`.
- **A gitignored TOC** could look like state hidden from git (III, IX). It is derived per
  host by design (006), its absence is a reported finding, and consumers refuse without it.
- **`consumers.yaml` in mneme** could look like a central registry (VI). It is read only by
  status and creates no runtime dependency. A consumer works or refuses on the TOC alone.

## Project Structure

### Documentation (this feature)

```text
specs/007-declared-campaign-corpus/
├── plan.md              # This file
├── research.md          # Phase 0 — binding decisions R1–R10
├── data-model.md        # Phase 1 — entities, finding states, validation rules
├── quickstart.md        # Phase 1 — validation scenarios 1–7
├── contracts/
│   ├── corpus-yaml.md               # the authority (.mneme/corpus.yaml)
│   ├── toc-json.md                  # the TOC + consumer obligations
│   ├── cli.md                       # mneme corpus group + mp deltas + MCP tool
│   ├── mempalace-cli-additions.md   # mine --files-from, sources, forget
│   └── consumers-yaml.md            # the consumer inventory
├── checklists/
│   └── requirements.md  # spec quality checklist
└── tasks.md             # Phase 2 (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
mneme/
├── corpus/                  # NEW package — corpus is not mempalace-specific (FR-001a)
│   ├── __init__.py
│   ├── config.py            # load/validate .mneme/corpus.yaml → CorpusConfig (rules 1–8)
│   ├── resolve.py           # CorpusConfig → ResolvedCorpus (git check-ignore, ls-files -t,
│   │                        #   symlink/extension checks, mined_as)
│   ├── toc.py               # write/read/verify corpus.toc.json; .gitignore append
│   ├── compare.py           # TOC × sources × mined record → corpus findings (FR-015)
│   ├── consumers.py         # load consumers.yaml, compliance
│   └── cli.py               # `mneme corpus` group (init/check/toc/current/consumers)
├── mempalace/
│   ├── runner.py            # ADD mine(files_from=, wing=), sources(), forget()
│   ├── render.py            # CHANGE: corpus campaigns render root mempalace.yaml (palace +
│   │                        #   rooms), the TOC, canon_wings/index_wings (+ transitional
│   │                        #   canon_wing); remove stale per-wing renders
│   ├── authority.py         # CHANGE: dual-authority check when corpus.yaml exists
│   ├── refresh.py           # CHANGE: per-kind --files-from mines; write mined record
│   ├── corpus_record.py     # NEW: <store>/mneme-corpus-mined.json (sibling of mine_record)
│   ├── prune.py             # CHANGE: corpus deletion set → forget; sparse-safe
│   ├── conform.py           # ADD corpus row + fleet consumers row; corpus campaigns'
│   │                        #   index row from compare.py
│   ├── bringup.py           # CHANGE: corpus-aware first mine
│   └── recipe.py            # CHANGE: parse recipe v3 `kinds:`
├── recipes/
│   ├── mempalace.recipe.v3.yaml   # NEW: kinds (name, default_trust, rooms_hint)
│   └── consumers.yaml             # NEW: GM-reviewed inventory (seeded from R9)
├── mcp/server.py            # ADD corpus_files(campaign, kind)
└── cli.py                   # add_typer(corpus_app, name="corpus")

tests/
├── unit/          # config validation table (every rule), resolve (sparse/symlink/gitignore/
│                  #   shared-file), toc stamp + freshness, compare state matrix (SC-004),
│                  #   prune deletion set
├── integration/   # render→refresh→status on a fixture campaign with decoys (quickstart 1–5);
│                  #   migration from a wing-model authority (quickstart 6); real-binary lane
└── fixtures/      # stub_mempalace: --files-from, sources --json, forget
```

**Structure Decision**: Single project, with one new package, `mneme/corpus/`. The corpus
has consumers beyond mempalace (FR-001a), so its configuration, resolution and TOC sit
beside `mneme/mempalace/`, not inside it. `mneme/mempalace/` only gains the code that
turns the TOC into mines, status rows and prunes. The wing-model code paths stay intact and
are selected when `corpus.yaml` is absent.

## Dependencies

1. **mempalace first.** The three CLI additions (`contracts/mempalace-cli-additions.md`) go
   on `kostadis-dev`, then the hypostasis pin is bumped (the PR #58 pattern). mneme's corpus
   path is gated on the installed mempalace offering them. If they are absent, the result is
   `UNKNOWN` with "mempalace too old for corpus mining", never a fallback to the wing model
   for a campaign that has declared a corpus.
2. **GM review of the seeded inputs is complete** (R2, R6 ratified; R9 inventory reviewed
   and written to `mneme/recipes/consumers.yaml`, all on 2026-10-23).
3. **CampaignGenerator follow-ups** (separate repo):
   - read `canon_wings`
   - replace `documents[]` and `grounding_bundle.py`'s hardcoded names with TOC reads
   - convert the hardcoded and probing summary/NPC readers (R9)
4. **Skills follow-ups**: `~/.claude/skills`, both `gm-assistant` copies, and the zvec-grep
   index behind `/campaign-recall`. Each becomes a compliant consumer by reading the TOC.

Items 3 and 4 do not block this feature. Until each lands, it shows as non-compliant owed
work (FR-024, SC-009).

## Execution Model

Decided by the GM on 2026-10-23. It binds `/speckit-tasks` and `/speckit-implement` for this
feature.

- **Worktree and branch**: all work happens in the worktree `~/src/mneme-007` on branch
  `007-declared-campaign-corpus`, never in the `~/src/mneme` checkout on `main`.
- **Orchestrator: Opus** (the main session). It owns task sequencing, the human checkpoints,
  and every precision decision the spec reserves for the GM. It writes each implementation
  brief and verifies each result against `tasks.md` and the contracts. It does not delegate
  scope, ordering or attribution decisions.
- **Implementers: Sonnet 5.5 at medium effort.** Each task (or tightly coupled group of
  tasks) is handed to a subagent running `claude-sonnet-5-5` at `medium` effort. The brief
  carries the task, the files it may touch, the contracts it must satisfy and the tests that
  prove it. Phases with no shared files can run in parallel.
- **Gate after each phase**: Opus runs `ruff check` and `pytest` itself and reads the diff
  before the next phase starts. A failing gate goes back to an implementer with the
  failure, never forward. Never run pytest under `git rebase --exec` (tests inherit
  `GIT_DIR`).
- **Cross-repo order**: the mempalace CLI additions (`contracts/mempalace-cli-additions.md`)
  are implemented first, on mempalace `kostadis-dev`, in their own worktree. The hypostasis
  pin bump comes next. mneme corpus work that calls the new verbs starts only after that.
- **Code review is a planned phase, not an afterthought.** After the last implementation
  phase and before any PR, Opus runs `/code-review` on the branch diff. Each finding is
  either fixed (by an implementer, then re-gated) or recorded with the reason it was left
  alone. The PR is opened only after that review is clean.
- **Human checkpoints stay human.** Each campaign's `corpus.yaml`, any change to
  `mneme/recipes/consumers.yaml`, and any `mp prune --confirm` on a live palace are the
  GM's. No subagent performs them.

## Complexity Tracking

> No constitutional violations — section intentionally empty.
