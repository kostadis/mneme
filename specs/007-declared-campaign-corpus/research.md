# Research: Declared Campaign Corpus

Binding decisions for feature 007. Each was resolved against the code on 2026-10-23; the
mempalace facts cite `~/src/Mempalace` on `kostadis-dev`, read (not executed) unless noted.

---

## R1. How mneme makes mempalace mine an exact file list

**Decision**: Add a `--files-from FILE` option to `mempalace mine`, exposing the `files`
parameter that `miner.mine()` already accepts (`miner.py:2362-2374`, used at `:2453`:
`if files is None: files = scan_project(...)`). mneme mines each kind as
`mempalace --palace P mine <campaign_root> --wing <kind> --files-from <list>`, where `<list>`
is that kind's mined files from the TOC (R5).

**Rationale**:
- A wing is fixed per mine (`wing = wing_override or config["wing"]`, `miner.py:2449`), and
  `--wing` already exists on the CLI (`cli/parser.py:198`). Per-kind mines with `--wing <kind>`
  make the kind a drawer's **wing**, which mempalace stores on every drawer
  (`_build_drawer_metadata`, `miner.py:1761-1828`). FR-007's "each drawer records its kind" is
  then met with no new metadata field.
- Passing the list bypasses `scan_project` entirely, so `.gitignore`, `.mempalaceignore`,
  `SKIP_DIRS` and the root wing play no part. The corpus cannot fail open, by construction.
- mneme drives mempalace only by subprocess (`runner.py:1-6`, Principles VII/VIII). The
  Python API already has the capability; only the CLI lacks it. Exposing an existing
  parameter is the smallest change that removes the constraint (Principle VIII).

**Alternatives considered**:
- *Allowlist `.mempalaceignore` using negation* (`*`, `!/docs/`, `/docs/*`, `!/docs/npcs/`,
  `!/docs/world_state.md`). The matcher supports `!` with last-match-wins (`miner.py:330`,
  `:406-410`), and the traced pattern set works. It is also consistent with `mempalace sync`,
  which reclassifies drawers from the ignore files only (`sync.py:304-308`). **Rejected**:
  one ignore file governs a whole mine, and a mine has one wing, so kinds cannot be separated.
  Grounding files and `party.md` share `docs/`, and only one `mempalace.yaml` can sit in a
  directory. The traces are also unexecuted, and `.mempalaceignore` at the root silently
  switches off `.gitignore` reading for the whole tree (`detect_ignore_filename`, `:275-296`).
- *`--include-ignored` on top of `*`*. It only bypasses filters, never restricts
  (`is_force_included`, `:498-519`). **Rejected**: `sync` knows nothing about
  `include_ignored` (no references in `sync.py`), so `sync --apply` would delete every
  force-included drawer as "gitignored".
- *One `corpus` wing, kind as room*. **Rejected**: room routing is heuristic. Folder and
  filename matches come first, then keyword counts in the first 2000 characters
  (`detect_room`, `miner.py:630-660`). Kind membership is a precision decision and cannot rest
  on a keyword score.

---

## R2. A file can be mined under only one kind

**Finding**: re-mining a changed file deletes its old drawers in every wing:
`collection.delete(where={"source_file": source_file})` (`miner.py:2078`, `:2107`), with no
wing filter. If one file were mined under two kinds, each kind's mine would wipe out the
other's drawers.

**Decision (GM-ratified 2026-10-23)**: a file declared under two kinds appears under **both**
kinds in the TOC, because consumers asking for either kind must get it. It is **mined once**,
under one kind. Which kind mines it is a precision decision, so mneme does not pick one:
- a file declared under more than one kind is `invalid: ambiguous-mining-kind` until the
  GM's corpus configuration names the mining kind (`mined_as: <kind>` on one of the two
  declarations, see `contracts/corpus-yaml.md`);
- `docs/party.md` declared as both `party` and `grounding` is the expected case.

**Alternatives considered**: picking a kind silently, e.g. "a direct file entry beats a
directory entry" or "first declared wins". **Rejected**: that is mneme inferring scope.

---

## R3. Listing drawer sources, and detecting unmined and stale files

**Finding**: mempalace has no CLI that lists distinct `source_file`s. The internals exist:
`sync._iter_drawer_metadata(col, wing)` (`sync.py:313-330`) and backend
`facet_counts("source_file", where={"wing": W})` (`backends/base.py:705`, implemented in
`sqlite_exact.py:1269`). `source_file` is absolute (`miner.py:1925`), and `source_mtime` is
stored. **There is no content hash for project drawers**; only `convo_miner.py:264` has one.

**Decision**:
1. Add `mempalace sources [--wing W] --json`. It prints one record per distinct
   `(wing, source_file)` with `source_mtime` and the drawer count. It is read-only.
2. mneme records **what it mined**, with a sha256 per file, in a derived store-side record
   `<store>/mneme-corpus-mined.json`. This is the sibling of `mneme-last-mine.json`
   (`mine_record.py:1-6`) and has the same lifecycle: `regenerate` wipes it. It is written
   only after a mine succeeds.
3. The status classification (FR-015) compares three sets: the TOC, the `sources` listing,
   and the mined record.
   - **undeclared**: in `sources`, not in the TOC.
   - **unmined**: in the TOC, not in `sources`.
   - **stale**: TOC sha256 ≠ mined-record sha256.
   - **unknown**: `sources` failed or did not parse, or the record is unreadable.

**Rationale**: mtime is not a content fact. A `git checkout` or a sparse-checkout widening
rewrites mtimes without changing content, so mtime alone would report false staleness
(Principle I). A sha256 taken at mine time is what the TOC already carries, so one
comparison answers the question.

**Alternatives considered**: `mempalace sync --dry-run` (today's index row, `conform.py:202`).
**Rejected** for corpus campaigns: it reports only missing or gitignored drawers, plus the
top-N sources (`runner.py:34-46`). It cannot see undeclared-but-present files, unmined files
or changed files.

---

## R4. Pruning drawers from files outside the corpus

**Finding**: `mp prune` deletes through `mempalace sync --apply`, which deletes only drawers
whose source is missing or gitignored (`runner.py:237-275`). A drawer from a file that still
exists but is outside the corpus is neither, so sync cannot delete it.

**Decision**: add `mempalace forget --sources-from FILE [--apply]`. It deletes the drawers
whose `source_file` is in the list, wraps the existing `delete(where={"source_file": …})`
path (and `tool_delete_by_source`, `mcp_server/tools_write.py:845`), and defaults to dry-run.
For corpus campaigns, `mneme mp prune` computes the exact set itself:
`undeclared ∪ (missing − not-materialized)` (R7). It shows the set in the preview and passes
it to `forget`, under the existing `--confirm --expect N` and backup protocol
(`prune.py:51-60`), then re-verifies with `sources`.

**Rationale**: mneme owns the classification, so the deletion set is the set the GM
reviewed, exactly, and not mempalace's separate idea of what is orphaned. Prune keeps its
Principle I shape: preview, bind the count, back up, apply, re-verify.

**Alternatives considered**: `sync --allow-from FILE`. **Rejected**: it still mixes
mempalace's "missing" classification into the deletion, and that is wrong for sparse
checkouts (R7).

---

## R5. The TOC: location, format, tracking

**Decision**:
- Path: `<campaign>/.mneme/corpus.toc.json`. JSON, so any consumer in any language can read
  it without mneme (FR-012).
- **Not tracked in git.** On render, mneme appends it to the campaign's `.gitignore`. It is
  host-local: it records what *this* checkout resolves to, sparse gaps and per-file hashes
  included. Feature 006's rule is that anything tracked must be true on every host, which a
  per-host resolution is not.
- Gitignoring it does not interact with mining or prune. `.mneme/` is a baseline exclusion
  (`recipe v2 baseline_exclusions`), and corpus mining no longer scans the tree (R1).
- **Stamp**: the TOC carries `corpus_sha256`, the sha256 of the exact bytes of
  `.mneme/corpus.yaml`, plus the `recipe_version` it was resolved against. A consumer
  verifies freshness by hashing `corpus.yaml` itself. That rule is in the contract, so
  checking freshness requires no mneme code (FR-011, FR-022).

**Alternatives considered**:
- *Tracked TOC*. **Rejected**: two hosts with different sparse cones would write different
  TOCs, the same ping-pong 006 removed.
- *In the store folder*. **Rejected**: consumers know the campaign directory, not the palace
  path, and resolving the path needs `data_roots.mempalace` (006).

---

## R6. Where the standard kinds live

**Decision**: the standard kinds are defined in a new recipe version, `mempalace.recipe.v3.yaml`,
under a `kinds:` section. Each kind has a name, a default trust and room hints. Adoption goes
through the existing `mp publish --recipe 3.0.0` / `mp adopt` flow, so adding a standard
kind later is a recipe change (spec Assumptions).

**Defaults (GM-ratified 2026-10-23)**:

| Kind | Default trust |
|---|---|
| `npcs` | authoritative |
| `summaries` | authoritative |
| `party` | authoritative |
| `grounding` | authoritative |
| `prep` | reference |

Trust keeps its existing meaning. It is descriptive, except that `authoritative` selects the
canon wing for CampaignGenerator's search face (`render.py:154-170`). With several
authoritative kinds, the CG face needs a list of canon wings, not one: see R8.

---

## R7. Sparse checkouts: "not checked out here" is not "removed"

**Decision**: for each declared path missing from the working tree, mneme asks git:
- `git ls-files -t -- <path>` reports `S` (skip-worktree) → **not-materialized**. It is listed
  in the TOC under the kind's `not_materialized`, it is not an error, and its drawers are
  never pruned.
- Tracked in neither the index nor HEAD → **missing**. This is a configuration error that
  names the path.
- Not inside a git work tree → **missing**, with no sparse classification (reported as such).

Observed: `~/toee/toee` is a sparse checkout with its cone at the campaign directory. All
1,236 tracked files under `docs/` show `H` (present), so today nothing declared is
skip-worktree. The case still matters for out-of-the-abyss and future cones.

---

## R8. Faces after the change

**Decision**:
- When `.mneme/corpus.yaml` exists, the mempalace authority (`.mneme/mempalace.yaml`) keeps
  `campaign`, `recipe_version`, `store` and `dispositions`. **`wings:` and `extra_exclusions:`
  must be absent.** If they are present, that is `invalid: dual-authority` naming both files
  (FR-001a, Principle V). Wings are derived: one per declared kind, with `name = kind`.
- Mining no longer needs the per-wing `mempalace.yaml` + `.mempalaceignore` renders for corpus
  campaigns. mneme renders one root `mempalace.yaml`, carrying `palace: <alias>` (the CLI
  pointer, `render.py:67-79`, still needed for walk-up resolution) and the rooms. The old
  per-wing renders are removed on the first corpus render, and status reports leftovers as
  drift.
- The CampaignGenerator search face (`config.yaml` `mempalace:`) becomes
  `canon_wings: [<authoritative kinds>]`, `index_wings: [<other kinds>]`. Today it is a single
  `canon_wing`. CG reads one canon wing today, so **this is a CG change**. GM decision
  (2026-10-23): no transitional `canon_wing` is written. CG reading `canon_wings`, and
  fixing every query that names old wings, ships before any campaign gets a
  `corpus.yaml`.
- `.mcp.json` and the global alias faces are unchanged; they name the palace, not files.

---

## R9. Consumers: inventory, compliance, conversion

**Finding** (from a read-only sweep on 2026-10-23, **unreviewed**): roughly 20 CampaignGenerator
consumers and 30 Claude skills read campaign files directly. Only four use the palace
(`rlm/mcp_server` search tools, `arc_triggers`, `dossier_proposer`,
`phandalin-chapter-release`). Summaries are located five different ways (`summaries/`,
`docs/summaries/`, a probe of both, a `summaries.md` bible at three paths, "the cwd").
Party data has two names (`party.md`, `party_state.md`). Two consumer-side mechanisms already
select files and must not survive as second authorities:
- **CG `config.yaml` `documents[]`** (label → path, `campaignlib/config.py:294`), used by
  `prep`, `check_consistency` and the campaign MCP server.
- **CG `grounding_bundle.py:27-30`**, the four grounding names hardcoded.

**Decision**:
- The inventory lives in mneme as `mneme/recipes/consumers.yaml`, versioned with the recipe.
  Each entry records: name, repo and entry point, kinds used, mode (`palace` | `toc` |
  `independent`) and evidence (`file:line`). Status computes compliance from mode.
  Classification is GM-maintained.
- **The sweep above is a first-pass LLM extraction. Per the LLM Pipeline Design Rule it seeds
  a draft the GM reviews before it is committed.** It does not feed status unreviewed. The GM
  chose (2026-10-23) to review it on a private review page grouped by repo; `consumers.yaml`
  is written from the GM's marks only. **Done 2026-10-23**: 52 consumers kept (49
  independent, 2 palace, 1 partial); `cg.new_workspace`, `gm-module-inventory` and
  `gm-voice-reconstruction` dropped as not consumers; the unread gm-assistant batch row was
  split into `gm-quest-log`, `gm-social-encounter` and `gm-statblock` after a real read.
- Status reports non-compliant consumers once, at fleet level, with a per-campaign pointer.
  The consumers are shared, not per campaign.
- `mneme corpus toc` (CLI) and a `corpus_files(campaign, kind)` tool in `mneme mp mcp` are the
  two convenience readers. Reading the JSON directly is equally compliant.
- Converting each consumer happens in its own repo (CG, `~/.claude/skills`, `gm-assistant`,
  the zvec-grep index behind `/campaign-recall`). Each conversion is a follow-up issue. When
  CG's `documents[]` and grounding bundle are converted, they read the TOC, so the second
  authority is removed rather than kept in sync.

---

## R10. Migration from the wing model

**Decision**:
- No corpus configuration → status `corpus: undeclared (owed)`. Mining stays on the wing
  model, unchanged (FR-019).
- `mneme corpus current CAMPAIGN` lists the files the current palace actually holds, from
  `sources`, grouped by wing. It is read-only (FR-020). It does not draft a `corpus.yaml`:
  mapping files to kinds is the GM's decision.
- `mneme corpus init CAMPAIGN` writes a skeleton `corpus.yaml` listing the standard kinds as
  comments, with **no paths**. It refuses if the file exists.
- First render after the GM writes `corpus.yaml`:
  1. The wings are re-derived and the old per-wing renders removed.
  2. Status then shows the old palace's drawers outside the corpus as `undeclared`, with a
     `mp prune` remedy.
  3. Nothing is deleted until the GM confirms the prune.

---

## Dependencies

1. **mempalace (`kostadis-dev`)**: three CLI additions: `mine --files-from`, `sources --json`
   and `forget --sources-from`. The first is a thin exposure of an existing parameter; the
   other two wrap existing internals (R3, R4). They ship first, then a hypostasis pin bump,
   as with PR #58.
2. **CampaignGenerator**: reading `canon_wings` (R8), and the TOC follow-ups (R9).
3. **Real-binary test**: the R1–R4 behaviour is verified against real mempalace through the
   existing slow e2e lane (`tests/integration/test_real_mempalace_e2e.py`,
   `MNEME_REAL_MEMPALACE_VENV`). Unit tests use `tests/fixtures/stub_mempalace.py`, extended
   with the three subcommands.
