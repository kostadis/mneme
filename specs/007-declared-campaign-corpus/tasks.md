---

description: "Task list for feature 007 — declared campaign corpus"
---

# Tasks: Declared Campaign Corpus

**Input**: Design documents from `specs/007-declared-campaign-corpus/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R10), data-model.md, contracts/, quickstart.md

**Tests**: Included. The plan's Testing section and quickstart scenarios 1–7 call for unit and
integration tests, and SC-004 requires a state-matrix test.

**Organization**: Grouped by user story (spec.md US1–US5) so each story can be built and
verified on its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US5 from spec.md
- **Who does it** (plan § Execution Model): every task goes to a **Sonnet 5.5 (`medium`)
  implementer** unless marked **(Opus)** (the orchestrator does it) or **(GM)** (a human
  checkpoint; no agent performs it).
- **Paths**: mneme tasks are relative to the worktree `~/src/mneme-007`. mempalace tasks are
  relative to the worktree `~/src/Mempalace-007` (created in T001).

## Rules every implementer brief carries

- Read the task's contract file(s) before writing code. The contracts are binding.
- mneme never imports mempalace. It calls the CLI through `mneme/mempalace/runner.py`
  (Principles VII/VIII).
- Unknown is never OK. Anything unverifiable is reported as unknown or unverified (FR-017).
- Never run pytest inside `git rebase --exec`.
- Match the surrounding code's style. Comments are sparse and cite the FR or research item
  they implement (as in `prune.py`, `conform.py`).

---

## Phase 1: Setup

**Purpose**: Workspaces and skeletons.

- [X] T001 (Opus) Create the mempalace worktree: `git -C ~/src/Mempalace worktree add -b feat/corpus-cli ~/src/Mempalace-007 kostadis-dev`. Mempalace work always branches from and merges back to `kostadis-dev`, never `main` (`~/src/CLAUDE.md`).
- [X] T002 [P] Create the empty package `mneme/corpus/__init__.py` with a module docstring naming feature 007 and stating that the corpus is campaign-level, not mempalace-specific (plan § Structure Decision).
- [X] T003 [P] Create `mneme/recipes/mempalace.recipe.v3.yaml`. Copy v2's `mechanical:` and `scaffold:` unchanged, set `version: "3.0.0"`, and add a `kinds:` section: `npcs`, `summaries`, `party` and `grounding` with `default_trust: authoritative`, `prep` with `default_trust: reference`, each with a `rooms_hint` list. The header comment states that v3 adds kinds for declared-corpus campaigns and that wing-model campaigns keep working (research R6).

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: The mempalace CLI verbs, the runner, the corpus configuration, resolution and TOC.
Every user story needs these.

**⚠️ CRITICAL**: No user-story work starts until this phase is gated green.

### mempalace (`~/src/Mempalace-007`, contract `contracts/mempalace-cli-additions.md`)

- [ ] T004 Add `mine --files-from FILE` in `mempalace/cli/parser.py` and `mempalace/cli/cmd_mine.py`:
  - Read newline-separated paths (relative to DIR or absolute under it; `-` means stdin) and pass them as `miner.mine(files=…)` (`miner.py:2362`).
  - Report each missing, symlinked, non-regular or non-`READABLE_EXTENSIONS` path on the existing `SKIP: <rel> (<reason>)` channel.
  - Reject the flag combined with `--include-ignored` or `--no-gitignore`.
  - Tests go in the repo's existing mine tests.
- [ ] T005 Add `mempalace sources [--wing W] --json` (new `mempalace/cli/cmd_sources.py`, registered in `mempalace/cli/parser.py`):
  - Read-only. Print a JSON array of `{wing, source_file, source_mtime, drawers}`, one per distinct `(wing, source_file)`.
  - Use `facet_counts("source_file", …)` where the backend supports it, otherwise `sync._iter_drawer_metadata` (`sync.py:313-330`).
  - Exit non-zero with no JSON if the store cannot be opened.
  - Tests included.
- [ ] T006 Add `mempalace forget --sources-from FILE [--wing W] [--apply]` (new `mempalace/cli/cmd_forget.py`, registered in `mempalace/cli/parser.py`):
  - Dry run by default.
  - Delete only drawers whose `source_file` is listed, via the existing `delete(where={"source_file": …})` path.
  - Print `Sources: N`, `Drawers: M`, and one `  <path>  (<count>)` line per source, every source listed.
  - Exit non-zero on any failure.
  - Tests included.
- [ ] T007 (Opus) Gate the mempalace worktree: run its test suite and linter, read the diff against `contracts/mempalace-cli-additions.md`, then push `feat/corpus-cli` and open a PR into `kostadis-dev` via `mcp__github__create_pull_request`.
- [ ] T008 (GM) Review and merge the mempalace PR into `kostadis-dev`. mneme work that calls the new verbs is blocked until this lands.
- [ ] T009 Bump the mempalace pin in `hypostasis.example.yaml` (the `components.mempalace.pin` line) to the merged `kostadis-dev` commit, and update its comment to name feature 007's CLI additions. In the task report, tell the GM that each host's `~/.config/hypostasis/hypostasis.yaml` needs the same pin and a `hypostasis install`. This task does not touch host configs.

### mneme foundations

- [X] T010 [P] Extend the test double `tests/fixtures/stub_mempalace.py` and update its docstring:
  - `mine … --files-from F --wing W` logs the argv and appends `(W, abs path)` pairs to a state file named by `$MNEME_STUB_SOURCES_STATE`.
  - `sources --json` prints that state as the contract's JSON. `$MNEME_STUB_SOURCES=rc1` exits 1, and `garbage` prints non-JSON.
  - `forget --sources-from F [--apply]` reports per the contract. With `--apply` it also removes those sources from the state file.
- [X] T011 Add runner methods to `mneme/mempalace/runner.py`:
  - `mine_files(root, files, wing, palace, dry_run)` writes the list to a temp file and passes `--files-from`, then returns `MineResult` with skips parsed as today.
  - `sources(palace, wing=None) -> list[SourceRecord] | None` returns None (unknown) on rc≠0 or unparseable output, and never raises on a read.
  - `forget(sources, palace, apply)` returns a parsed report and raises `MempalaceError` on a failed apply.
  - Add `supports_corpus()`, which probes `mempalace --help` once for the three verbs.
  - Unit tests in `tests/unit/test_mp_runner_corpus.py`, against the stub.
- [X] T012 [P] Add the recipe kinds:
  - Add `KindDef(name, default_trust, rooms_hint)` to `mneme/mempalace/models.py` and `kinds: tuple[KindDef, ...] = ()` to `Recipe`.
  - Parse `kinds:` in `mneme/mempalace/recipe.py` `_parse`. v1/v2 yield no kinds.
  - Tests in `tests/unit/test_mp_recipe_v3.py`: v3 loads five kinds with the ratified trusts, v2 loads none, and `current()` returns v3.
- [ ] T013 Implement `mneme/corpus/config.py`:
  - Dataclasses `CorpusConfig`, `KindDecl`, and `load(campaign_dir, recipe) -> CorpusConfig` raising `CorpusConfigError(findings)`.
  - Enforce `contracts/corpus-yaml.md` and data-model validation rules 1–3 and 6 (the structural half: at most one `mined_as` per shared file, trust agreement), plus unknown-key rejection. Rule 8 (`empty-corpus`) needs resolution and belongs to T014.
  - Error codes: `unknown-kind`, `shadowed-kind`, `missing-trust`, `empty-declaration`, `path-escape`, `trust-conflict`, `ambiguous-mining-kind`, `campaign-mismatch`.
  - `corpus_sha256` is the sha256 of the raw file bytes.
  - Table-driven tests in `tests/unit/test_corpus_config.py`, one case per code (quickstart scenario 5).
- [ ] T014 Implement `mneme/corpus/resolve.py`:
  - `resolve(cfg, campaign_dir, recipe) -> ResolvedCorpus` per data-model § ResolvedCorpus.
  - Expand `dirs` recursively and classify each file as minable, non-minable (extension outside mempalace's readable set; mirror the list in a constant with a comment citing `miner.py:140-181`), not_materialized (`git ls-files -t` reports `S`) or missing.
  - Resolve symlinks: a declared symlink (or one inside a declared dir) that resolves to a regular file inside the campaign is minable, with `target` set to the resolved campaign-relative path. Symlinked directories are followed. Resolving outside the campaign gives `symlink-outside`, and resolving to a non-file gives `symlink-not-file`.
  - Emit `gitignored` findings (via `git check-ignore`, checked on both the declared path and the target).
  - Assign each file its mining kind (R2). Overlaps discovered only through `dirs` expansion are checked here: emit `ambiguous-mining-kind` (shared by more than one kind, with zero or several `mined_as` marks) and `trust-conflict`.
  - Emit `empty-corpus` when the whole declaration resolves to no files (data-model rule 8).
  - Tests in `tests/unit/test_corpus_resolve.py`, using a temporary git repo with sparse/skip-worktree, an in-campaign symlink through a symlinked dir (the out-of-the-abyss `docs/party.md → grounding/current/party.md` shape), an out-of-campaign symlink, a gitignored file, a `.pdf` and a file shared across kinds.
- [ ] T015 Implement `mneme/corpus/toc.py` per `contracts/toc-json.md`:
  - `build(resolved, cfg, recipe) -> dict`, `write(campaign_dir, toc)` (atomic write, then append `.mneme/corpus.toc.json` to the campaign `.gitignore` if it is missing), `read(campaign_dir)`.
  - The file is a **snapshot** (GM decision 2026-10-23: consumers re-resolve on read and never read it). `verify(campaign_dir, fresh) -> TocCheck` compares the snapshot with a fresh resolution and returns missing, stale (differs in stamp, file set or hashes, which covers a new file in a declared dir and a hand-edited file list) or ok. Status uses it for `toc-stale`.
  - `files_for(toc, kind)` distinguishes a kind that is not declared from one that is declared but empty.
  - Each file entry carries `target` when the declared path is a symlink (`contracts/toc-json.md`).
  - Tests in `tests/unit/test_corpus_toc.py`, including "file added to a declared dir after render" and "hand-edited `files[]` with the stamp kept", both reported stale.
- [ ] T016 Add the dual-authority check to `mneme/mempalace/authority.py`. When `.mneme/corpus.yaml` exists and `.mneme/mempalace.yaml` has `wings:` or `extra_exclusions:`, `load()` raises `AuthorityError` with `dual-authority`, naming both files (research R8, FR-001a). When `corpus.yaml` is present, `wings` may be absent; the existing "no wings" validation must not fire. Tests go in the existing authority unit tests.
- [ ] T017 Guard every wing-model mining path against corpus campaigns. In `mneme/mempalace/refresh.py` (`_refresh_one`), `mneme/mempalace/provision.py` (`first_mine`), `mneme/mempalace/bootstrap.py` (`:105` loop) and `mneme/mempalace/conform.py` (`check_dir`, `:358-365`), when `.mneme/corpus.yaml` exists, never iterate `wing_dirs`. Those paths now either hand off to the corpus path (refresh, first_mine) or refuse with "corpus campaign — mining is driven by .mneme/corpus.yaml". The reason: a corpus campaign keeps a root `mempalace.yaml`, so `_existing_wing_dirs` returns the campaign root and a wing-model mine would mine the whole tree, the exact fail-open this feature removes. Unit tests in `tests/unit/test_corpus_guards.py` assert that no `mine <campaign root>` without `--files-from` is ever issued for a corpus campaign (check the stub log).
- [ ] T018 (Opus) Gate Phase 2: `ruff check hypostasis mneme tests` and `pytest` in `~/src/mneme-007`. Read the diff against the contracts before Phase 3.

**Checkpoint**: the corpus can be loaded, validated, resolved and published as a TOC, and the runner can drive the new verbs.

---

## Phase 3: User Story 1 — The palace contains exactly the curated files (Priority: P1) 🎯 MVP

**Goal**: For a campaign with `corpus.yaml`, mining produces drawers from declared files only, with one wing per kind.

**Independent Test**: quickstart scenario 1. A fixture campaign with decoys, after render and refresh, has `sources` equal to the six declared files and nothing else.

- [ ] T019 [P] [US1] Implement `mneme/mempalace/corpus_record.py`, sibling of `mine_record.py`, same atomic-write and error style. It reads and writes `<store>/mneme-corpus-mined.json` (`{schema, campaign, mined_at, corpus_sha256, files: {relpath: {kind, sha256, target}}}`, with `target` the resolved path actually mined; T023 depends on it) and merges per kind after each successful kind mine (research R3).
- [ ] T020 [US1] Extend `mneme/mempalace/render.py` for corpus campaigns (`corpus.yaml` present):
  - Write the root `mempalace.yaml`, stamped, with `palace: <alias>` plus the union of rooms from the recipe kinds.
  - Write the TOC via `mneme/corpus/toc.py`.
  - Delete leftover per-wing `mempalace.yaml` and `.mempalaceignore` renders, but only files carrying mneme's stamp.
  - Write `config.yaml` `mempalace: {canon_wings, index_wings}`. No `canon_wing` key: the CG change ships first (R8, plan Dependency 6).
  - Make `coherent()` and `render_faces()` cover the corpus artifacts.
  - The wing-model path is unchanged.
  - Tests in `tests/unit/test_mp_render_corpus.py`.
- [ ] T021 [US1] Extend `mneme/mempalace/refresh.py` for corpus campaigns:
  - Refuse with an unknown result if `runner.supports_corpus()` is false (plan Dependency 1).
  - Run the embedder guard, then for each kind call `runner.mine_files(campaign_dir, <the resolved targets of minable files whose mined_as is this kind>, wing=kind)`. Always pass targets, never symlinks.
  - Update the corpus record after each successful kind. Keep the GH #31 skip record.
  - `--dry-run` prints the per-kind file lists and mines nothing.
  - A failed kind stops the run and writes no clean record (mirror `_refresh_one`).
  - **Re-mine on content change** (analysis U4): mempalace skips a file whose source_file and mtime match a mined group, so a same-mtime edit would be silently skipped while the record's new sha read as mined. For every file whose current sha256 differs from the record (or that has no record), `runner.forget([target], apply=True)` first, then mine it. Write a file's sha to the record only for files mined in this run, or already recorded with the same sha.
  - Refresh resolves the corpus itself, with the same `resolve.py` the readers use, and rewrites the TOC snapshot afterwards (analysis U7).
  - **Write isolation** (FR-009): refresh writes only to the store, the mneme records and the TOC snapshot, never campaign content. A test asserts that the campaign tree is byte-identical apart from `.mneme/corpus.toc.json`.
- [ ] T022 [US1] Re-home files mined under the wrong wing, in `mneme/mempalace/refresh.py`. mempalace's already-mined check matches on `source_file` and mtime only, never on wing (`Mempalace/mempalace/palace/mined.py:59`), so `mine --files-from --wing <kind>` skips a file already mined under an old wing (e.g. `docs/npcs/agatha.md` under the root wing `obelisk`). Before each kind's mine, call `runner.sources()`. Collect corpus files whose current wing differs from their `mined_as`. `runner.forget(<those>, apply=True)` them, then mine. Report the re-homed count, and list them in `--dry-run`. This applies only to files in the TOC. Undeclared sources are left for prune. Unit tests in `tests/unit/test_mp_refresh_corpus.py`, using a stub state that has a file under a foreign wing.
- [ ] T023 [US1] Replace re-pointed symlinks on refresh, in `mneme/mempalace/refresh.py`. For each corpus file whose current resolved `target` differs from the `target` in `mneme-corpus-mined.json` (a grounding promotion moved `docs/grounding/current`), `runner.forget([<old target>], apply=True)`, then mine the new target, in the same refresh. No prune and no confirmation: the declared membership is unchanged (spec Clarifications, 2026-10-23). Report "replaced N re-pointed files" and list them in `--dry-run`. Only old targets recorded for a still-declared path are forgotten; anything else is left for prune. Integration test in `tests/integration/test_corpus_mining.py`: build two generation dirs plus a `current` symlink, mine, re-point `current`, refresh, and `sources` then holds only the new generation's files.
- [ ] T024 [US1] Make `mneme/mempalace/bringup.py` use the corpus path when `corpus.yaml` exists: write the mempalace authority with no `wings:` if the campaign has none (out-of-the-abyss has no `.mneme/` today), provision, corpus render, per-kind first mine, then backup. Otherwise it is unchanged. Test: bringup from `corpus.yaml` alone yields drawer sources equal to the resolved corpus (SC-003, out-of-the-abyss case).
- [ ] T025 [P] [US1] Integration test `tests/integration/test_corpus_mining.py` for quickstart scenario 1:
  - Set up the fixture campaign in a temp git repo, with decoys `docs/campaign_state_draft.md`, `docs/party_draft.md`, `docs/reviews/x.md` and `summaries/raw.md`, using the stub.
  - Assert wings `npcs`/`summaries`/`grounding` and that no decoy is mined.
  - Assert that a new `docs/new_generated/y.md` adds nothing.
  - Assert that `mined_as` puts a shared `docs/party.md` in exactly one wing.
- [ ] T026 (Opus) Gate US1: ruff, pytest, diff review.

**Checkpoint**: MVP. Declared-corpus campaigns can no longer fail open.

---

## Phase 4: User Story 2 — Status proves the palace equals the corpus (Priority: P1)

**Goal**: `mp status` reports a corpus row with every finding, its remedy, and never a false OK. Prune deletes exactly the reviewed set.

**Independent Test**: quickstart scenarios 2 and 3.

- [ ] T027 [US2] Implement `mneme/corpus/compare.py`:
  - `compare(toc, sources, record, campaign_dir) -> CorpusFindings`, covering undeclared-drawers, unmined, stale (TOC sha differs from record sha), missing, invalid, toc-stale and unknown, per the data-model state diagram.
  - `not_materialized` is never a finding.
  - Sources outside the campaign root are `out_of_scope`.
  - OK only when there are no findings (FR-017).
- [ ] T028 [US2] Add a **wrong-wing** finding to `mneme/corpus/compare.py`: a corpus file whose drawers sit in a wing other than its `mined_as`, with remedy `mp refresh` (which re-homes it, T022). A file present in the right wing and in another wing reports both wrong-wing and, if undeclared elsewhere, nothing extra. Add the case to the state matrix in `tests/unit/test_corpus_compare.py`. The data-model state diagram already lists `WRONG-WING`.
- [ ] T029 [P] [US2] State-matrix unit tests `tests/unit/test_corpus_compare.py` (SC-004): one case per finding, combined findings, and "unknown when sources is None or the record is unreadable". Every non-matching case must be not-OK.
- [ ] T030 [US2] Wire into `mneme/mempalace/conform.py`:
  - In `_campaign_rows`, when `corpus.yaml` exists, add a `corpus` row (new `State` values as needed in `mneme/mempalace/models.py`) whose note lists each finding with counts, files (truncated past 10 with a count), and remedy (`mp prune` / `mp refresh` / edit `corpus.yaml` / `mp render`), per FR-015/016.
  - Replace the `index` row for corpus campaigns with one derived from the same comparison.
  - The wing-model path is untouched.
- [ ] T031 [US2] Extend `mneme/mempalace/prune.py` for corpus campaigns:
  - The deletion set is `undeclared ∪ (missing − not_materialized)`, computed by `compare.py`.
  - The preview lists every source with its drawer count. `--confirm --expect N` is bound to N drawers.
  - Back up first (unless `--no-backup`), apply `runner.forget(apply=True)`, then re-verify with `runner.sources()` and fail if any deleted source remains.
  - Not-materialized sources are never in the set (FR-018, R4, R7).
  - **Former-canon guard** (GM decision, 2026-10-23): refuse when the set includes drawers whose wing was `authoritative` before the corpus. Print each such wing with its file and drawer counts, and proceed only when every one is named with `--include-former-canon <wing>` (repeatable). The former wings come from `<store>/mneme-former-wings.json`, a derived record that mneme rewrites with `{wing: trust}` whenever it loads a wing-model authority that has a store (hook it into `authority.load` callers in `conform.py` and `refresh.py`). Write the record in `mneme/mempalace/former_wings.py` (data-model § FormerWingsRecord, FR-018a). If the record is absent, **every wing holding undeclared drawers** is treated as former canon (fail closed). That is keyed on which sources are undeclared, not on wing names, so an old wing named like a kind (obelisk's old `summaries` wing) is still caught. Tests in `tests/unit/test_mp_prune_corpus.py`: refused without the flag, proceeds with it, and the absent-record case.
  - Unit tests in `tests/unit/test_mp_prune_corpus.py`.
- [ ] T032 [US2] Make `mp regenerate` corpus-aware in `mneme/mempalace/backup.py` (`regenerate`, `:258-278`). For a corpus campaign, after clearing the store, first-mine through the corpus path (per-kind `--files-from`, writing a fresh corpus record) instead of `provision.first_mine`'s wing loop. Integration test in `tests/integration/test_corpus_status_prune.py`: regenerate a corpus campaign with decoys present, and `sources` afterwards equals the TOC exactly.
- [ ] T033 [P] [US2] Integration test `tests/integration/test_corpus_status_prune.py` for quickstart scenarios 2 and 3: every row of the scenario-2 table, then the prune preview, confirm and re-verify flow, and the skip-worktree survivor.
- [ ] T034 (Opus) Gate US2: ruff, pytest, diff review.

**Checkpoint**: US1 + US2 make the palace provably exact.

---

## Phase 5: User Story 3 — Every consumer reads the same file list (Priority: P2)

**Goal**: Three equivalent TOC readers (file, CLI, MCP), all applying the consumer obligations in `contracts/toc-json.md`.

**Independent Test**: quickstart scenario 4.

- [ ] T035 [US3] Create `mneme/corpus/cli.py` with a Typer app and `check` plus `toc [--kind K] [--json] [--write]` (`contracts/cli.md`). `toc` always resolves fresh from `corpus.yaml` and the disk (never from the snapshot) and exits non-zero on an invalid configuration. `--write` also refreshes the snapshot. This is the consumer entry point (FR-012). Register it in `mneme/cli.py` with `app.add_typer(corpus_app, name="corpus")`. Both take `--config` and `--dir` like `mneme mp`.
- [ ] T036 [P] [US3] Add an MCP tool `corpus_files(campaign: str, kind: str) -> dict` in `mneme/mcp/server.py`, beside `get_status`. It resolves fresh on every call (same code as `corpus toc`), looks the campaign up with `_discover.resolve()` (never `find()`; PR #61), and returns `{files}` or `{error: "invalid"|"not-declared", detail}`.
- [ ] T037 [P] [US3] Integration test `tests/integration/test_corpus_toc_readers.py` for quickstart scenario 4: `mneme corpus toc --json` and `corpus_files` return identical lists; a file added to a declared dir appears in both with no render; a hand-edited snapshot affects neither, and status reports `toc-stale`; an invalid `corpus.yaml` is refused by both; an undeclared kind gets "not declared", not `[]`.
- [ ] T038 [P] [US3] Add a "Declared corpus" section to `mneme/recipes/instructions/manage-mempalace.md`: the `corpus.yaml` shape, the TOC, the consumer obligations (read the TOC, refuse when stale), and `mined_as`. The `mneme mp mcp` server serves it.
- [ ] T039 (Opus) Gate US3: ruff, pytest, diff review.

---

## Phase 6: User Story 4 — Existing campaigns move to a declared corpus deliberately (Priority: P2)

**Goal**: Campaigns without a declaration are shown as owing one. The GM gets read-only input and a pathless skeleton. mneme never writes membership.

**Independent Test**: quickstart scenario 6, on a fixture first, then the live fleet.

- [ ] T040 [US4] Add `corpus current CAMPAIGN` (files the palace holds, from `runner.sources()`, grouped by wing; read-only; "no palace" when there is none) and `corpus init CAMPAIGN` (a skeleton `corpus.yaml` listing the standard kinds as comments, no paths; refuses if the file exists) to `mneme/corpus/cli.py` (FR-020, R10).
- [ ] T041 [US4] In `mneme/mempalace/conform.py`, a campaign with a mempalace authority but no `corpus.yaml` gets a `corpus` row `UNDECLARED (owed)` with the remedy `mneme corpus init`. Its other rows and wing-model mining are unaffected (FR-019). The owed state is **not** in `FAIL_STATES` (`mneme/mempalace/models.py:160`), so `mp status` still exits 0 (GM decision, 2026-10-23). A test asserts the exit code.
- [ ] T042 [US4] Define corpus-campaign behaviour for the wing-editing commands, and test each one:
  - `mp bootstrap` refuses: the campaign already has a corpus authority.
  - `mp migrate` refuses: migration plans edit wings, and corpus campaigns have none (FR-001a).
  - `mp publish` / `mp adopt` may only move `recipe_version` and must never write `wings:` or `extra_exclusions:` into a corpus campaign's `.mneme/mempalace.yaml`. Adopting a recipe whose standard kinds collide with a campaign kind reports `shadowed-kind` instead of writing.
  - `mp faces` and `mp render --check` use the corpus render (T020).
  - The changes go in `mneme/mempalace/bootstrap.py`, `mneme/mempalace/migrate.py`, `mneme/mempalace/publish.py` and `mneme/mempalace/proposals.py`/`cli.py` (adopt). Each refusal names the command and the reason.
  - Tests in `tests/unit/test_corpus_wing_commands.py`.
- [ ] T043 [P] [US4] Integration test `tests/integration/test_corpus_migration.py`, using a wing-model fixture palace with a root wing:
  - Status shows undeclared-owed.
  - `corpus current` lists today's files.
  - After a `corpus.yaml` is written, render, then status shows the old extra drawers as `undeclared-drawers`, and nothing is deleted before the prune is confirmed.
- [X] T044 [P] [US4] Produce one **corpus worksheet** per campaign, a read-only reference document the GM uses to write that campaign's `corpus.yaml` by hand, at their own pace. Nothing is run against the campaign and nothing is written into it. This task has no code dependency and can run at any time. Write `specs/007-declared-campaign-corpus/worksheets/{obelisk,toee,out-of-the-abyss}.md`, each surveying the sparse checkout the GM works in (`~/obelisk/obelisk`, `~/toee/toee`, `~/out-of-the-abyss/out-of-the-abyss`; state the path and git HEAD surveyed). Each worksheet contains, all as **observations, never proposals**:
  1. **What the palace mines today.** The current `.mneme/mempalace.yaml` wings (name, source, trust) and exclusions, and, if the palace is readable, the per-wing source counts. Note "no authority" for out-of-the-abyss. Flag every `authoritative` wing, because those drop out unless declared (e.g. `docs/chapters`).
  2. **Files at each standard kind's usual locations**, listed verbatim with counts: `docs/npcs/`, `docs/summaries/` and top-level `summaries/` (kept apart: published vs pipeline output), the four grounding files, `docs/party.md` / `docs/party/` / `docs/party_state.md` / per-PC files, `notes/` and `notes/sessions/`.
  3. **Look-alikes to decide on**: drafts (`*_draft*`, `*.candidate.*`), backups (`*.bak`, `*.old`), staging/extraction/review dirs (`*_extractions/`, `state_staging/`, `reviews/`, `summary_native/`, `archive/`), each with its path.
  4. **Files that would be shared across kinds** (e.g. `docs/party.md` as both party and grounding), each needing a `mined_as` choice.
  5. **Hazards**: symlinks, gitignored paths and skip-worktree (sparse) paths under any of the above, plus non-readable extensions (`.pdf`).
  6. **Candidate campaign kinds**: directories that hold true-looking material outside the five standard kinds (e.g. `docs/chapters`, backstory files, `voice/`).
  7. **A decision checklist** (one line per kind: which dirs/files, trust override?, `mined_as` for shared files), and a **blank `corpus.yaml` skeleton** with the standard kinds as empty entries and no paths filled in.

  The worksheet must not fill in membership or say "recommended". Opus reviews each one against the disk before handing it to the GM.
- [ ] T045 (Opus) Gate US4: ruff, pytest, diff review.
- [ ] T046 (GM) Live migration, one campaign at a time (obelisk, toee, out-of-the-abyss):
  - The GM writes each `corpus.yaml` from its worksheet (T044), at their own pace and in any order. `mneme corpus init` is optional; the worksheet's skeleton is enough. No agent writes or converts a campaign on the GM's behalf.
  - **Prerequisite (plan Dependency 6):** the CampaignGenerator change (reads `canon_wings`; no query names a pre-corpus wing) has shipped. No campaign gets a `corpus.yaml` before then.
  - Opus runs `mp render` and `mp status` and shows the prune preview.
  - The GM alone runs `mp prune --confirm --expect N`, then `mp refresh`, until `corpus: OK` (SC-003, SC-007).

---

## Phase 7: User Story 5 — See which consumers are not yet on the TOC (Priority: P3)

**Goal**: Status surfaces every non-compliant consumer from the GM-reviewed inventory.

**Independent Test**: quickstart scenario 7.

- [ ] T047 [US5] Implement `mneme/corpus/consumers.py`: load and validate `mneme/recipes/consumers.yaml` (`contracts/consumers-yaml.md`; unknown modes and unknown kinds are errors) and compute `compliant(c)` (palace/toc = yes, partial = partly, independent = no). Add `corpus consumers [--noncompliant]` to `mneme/corpus/cli.py`. Accept the contract's optional fields `reads`, `kinds_toc`, `other`, `note` (unknown fields are errors). Tests in `tests/unit/test_corpus_consumers.py`, including a test that the shipped file parses and contains 52 entries. Depends on T035 (shared `mneme/corpus/cli.py`).
- [ ] T048 (Opus drafts, GM approves) [US5] Add `reads:` path patterns to each of the 52 entries in `mneme/recipes/consumers.yaml`, from each entry's `entry` evidence: read the cited code or SKILL.md and record the paths exactly as the consumer reads them. Publish the draft on the existing review page (https://claude.ai/artifact/5jtLz4tFuf8pvqMxKnx1dy, one row per consumer with its proposed `reads:`). The GM marks each row. Only GM-approved paths are written to the file, and it is committed only after the GM approves the diff (GM checkpoint; the file is the GM's record).
- [ ] T049 [US5] Add one fleet-level `consumers` row to `mneme/mempalace/conform.py` `report()`, with the non-compliant count and the command to list them, plus, per campaign, each non-compliant consumer's `reads:` paths that fall outside that campaign's resolved corpus and the corpus files of its kinds it misses (FR-024). Depends on T030 and T041 (shared `conform.py`) and on the GM-approved `reads:` from T048. Like the undeclared row, it is owed work, not a failure: exit code 0, with a test.
- [ ] T050 (Opus, GM approves) Draft one follow-up issue per consumer repo: CampaignGenerator (including `documents[]`, `grounding_bundle.py`, `canon_wings`, and every query naming a pre-corpus wing; this issue is the T046 prerequisite), `~/.claude/skills`, gm-assistant, and the `/campaign-recall` zvec-grep index. Show the drafts to the GM. File them via `mcp__github__issue_write` only after the GM approves. Once filed, the GM approves an edit adding the `issue:` fields to `mneme/recipes/consumers.yaml`.

---

## Phase 8: Polish, review and release

- [ ] T051 [P] Document `mneme corpus` and the corpus behaviour of `mp render/refresh/status/prune` in `README.md` under the `mneme mp` section.
- [ ] T052 [P] Add a corpus scenario to `tests/integration/test_real_mempalace_e2e.py`, behind `MNEME_REAL_MEMPALACE_VENV`: real `mine --files-from`, `sources --json` and `forget` against a throwaway palace. This verifies the research R1–R4 behaviour against the real binary.
- [ ] T053 (Opus) Full gate: `ruff check hypostasis mneme tests`, `pytest`, and the real-binary lane with `MNEME_REAL_MEMPALACE_VENV` set.
- [ ] T054 (Opus) **Code review phase** (plan § Execution Model): run `/code-review` on the branch diff (`main...007-declared-campaign-corpus`). For each finding, either send it to a Sonnet implementer and re-gate (T053), or record why it is left as is in the PR description. Repeat until the review is clean.
- [ ] T055 (Opus, GM approves) Push `007-declared-campaign-corpus`, then open the PR via `mcp__github__create_pull_request`. The PR body includes the code-review outcome, the T046 migration results, and the follow-up issues from T050.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: none. T002 and T003 run in parallel; T001 is independent.
- **Foundational (Phase 2)**:
  - mempalace T004 → T005 → T006 run in sequence (shared `parser.py`), then T007, then T008 (GM), then T009.
  - The mneme foundations T010–T017 can start as soon as Phase 1 is done. They are tested against the stub. T017 (the wing-model guard) must land before any corpus mining runs.
  - Real-binary use waits on T009.
- **US1 (Phase 3)**: needs Phase 2. This is the MVP.
- **US2 (Phase 4)**: needs US1, because comparison needs corpus mining and the corpus record.
- **US3 (Phase 5)**: needs only Phase 2 (the TOC). It can run in parallel with US1 and US2.
- **US4 (Phase 6)**: T040–T043 need US2 (status rows). **T044 (the worksheets) has no dependency and can run immediately.** T046 (GM) needs US1, US2 and T009 merged and installed, and proceeds at the GM's pace, campaign by campaign.
- **US5 (Phase 7)**: needs Phase 2 plus `consumers.yaml`. T047 waits for T035 (both edit `mneme/corpus/cli.py`), and T049 waits for T030 and T041 (all edit `conform.py`). The `reads:` review (T048) can start any time.
- **Polish (Phase 8)**: needs every story wanted in this release. T054 code review precedes T055.

### Within each story

The implementation tasks come before their integration test, except tasks marked [P],
which touch separate files. The Opus gate closes each phase.

## Parallel Opportunities

- Phase 1: T002 ∥ T003.
- Phase 2: the mempalace chain (T004–T009) runs alongside the mneme chain (T010–T016). Within mneme, T010 ∥ T012. T013 → T014 → T015 are sequential (each builds on the last). T016 and T017 are independent of them.
- After Phase 2, three implementers can run at once: US1 (T019–T025), US3 (T035–T038) and US5 (T047–T049).
- Within US1: T019 ∥ T020. Within US2: T029 ∥ T033, once T027 and T031 land.

### Parallel example: after Phase 2

```text
Implementer A (Sonnet medium): US1  — T019, T020, T021, T022, T023, T024, T025
Implementer B (Sonnet medium): US3  — T035, T036, T037, T038
Implementer C (Sonnet medium): US5  — T047, T049
Opus: gates each story as it lands (T026, T039), then starts US2.
```

## Implementation Strategy

### MVP first

0. Any time, independently: T044, the per-campaign corpus worksheets, so the GM can start drafting `corpus.yaml` files before any code lands.
1. Phase 1 and Phase 2, including the merged mempalace PR (T008).
2. Phase 3 (US1). **Stop and validate** with quickstart scenario 1: declared campaigns can no longer fail open.
3. Phase 4 (US2), so the palace is provably exact and prunable.

### Then incremental

4. US3: one TOC for every reader.
5. US4: tooling, then the GM's live migration of obelisk, toee and out-of-the-abyss.
6. US5: compliance in status, plus follow-up issues for the consumer repos.
7. Polish, code review, PR.

## Notes

- **GM checkpoints** (T008, T046, T050, T055 approval) are never delegated. A subagent brief must not include them.
- Every task's implementer brief names the files it may touch. A change outside those files is sent back.
- Commit after each gated phase, on `007-declared-campaign-corpus` only.
