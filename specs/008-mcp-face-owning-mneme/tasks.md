# Tasks: MCP Face Bound to the Owning mneme (008)

**Input**: `specs/008-mcp-face-owning-mneme/` — plan.md, spec.md, research.md (R1–R9),
data-model.md, contracts/mcp-face.md, contracts/status-rows.md, quickstart.md

**Tests**: included. The quickstart §2 scenario table is the acceptance list, and the repo's
convention is that each behaviour change ships with unit tests.

**Execution model** (plan.md § Execution Model): Opus orchestrates and gates. Each task group
below is briefed to a Sonnet subagent (`model: sonnet`, `effort: medium`). After every phase,
Opus runs `ruff check .` + `pytest -q tests/unit tests/integration` and reads the diff. One
`/code-review` pass (Phase 7), then the PR, then leftovers are filed as issues (Phase 8).
No task edits `~/.config/hypostasis/hypostasis.yaml` or any real campaign under `~/`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US4 from spec.md

---

## Phase 1: Setup

- [X] T001 Confirm the worktree baseline is green before any change: in `~/src/mneme-008` run `ruff check .` and `pytest -q tests/unit tests/integration`; record the pass count in the Phase 1 gate note at the bottom of `specs/008-mcp-face-owning-mneme/tasks.md` (Opus, not delegated)

---

## Phase 2: Foundational (blocks all stories)

**Purpose**: the hypostasis key, the new State values, and the `mcpface` module skeleton that
every story builds on.

- [X] T002 [P] Add `campaign_shared_dirs: tuple[str, ...] | None = None` to `ConfigEntity` in `hypostasis/models.py` (`None` = undeclared, `()` = declared empty; keep frozen/dataclass style of neighbours)
- [X] T003 Parse top-level `campaign_shared_dirs` in `hypostasis/config.py` (`_build`/the function that returns `ConfigEntity`, ~line 205): absent → `None`; must be a list of strings; each a plain name (no `/`, not `.`/`..`, non-empty) else append a problem `campaign_shared_dirs: …`; pass to `ConfigEntity` (depends on T002)
- [X] T004 [P] Tests for T002–T003 in `tests/unit/test_config.py`: absent → `None`; `[]` → `()`; `[gm-assistant, scripts]` → tuple; non-list, `a/b`, `..` each produce a validation problem
- [X] T005 [P] Add `State.CLONE_ROOT_OWED = "clone_root_owed"` and `State.CLONE_ROOT_CONFLICT = "clone_root_conflict"` to `State` in `mneme/mempalace/models.py`; add `CLONE_ROOT_CONFLICT` to `FAIL_STATES`; add `CLONE_ROOT_OWED` to whatever set makes `row.ok` false but non-FAIL only if `CONSUMERS_OWED` is in it (mirror `CONSUMERS_OWED` exactly)
- [X] T006 [P] In `mneme/mempalace/conform.py::format_row` (~line 677) add `State.CLONE_ROOT_OWED` to the `todo` tuple alongside `CORPUS_UNDECLARED`, `CONSUMERS_OWED` (depends on T005)
- [X] T007 Create `mneme/mempalace/mcpface.py` with: `class McpBindingError(Exception)`; frozen dataclass `McpBinding(mneme_program: Path, mempalace_program: Path, config_path: Path, env: dict[str,str])`; `binding_for(entity, *, need_mempalace: bool) -> McpBinding` deriving `entity.venv/"bin"/"mneme"`, `entity.venv/"bin"/"mempalace-mcp"`, `entity.source_path` (all `.expanduser().resolve()`), `env=render.declared_mcp_env(entity.env)`; raise `McpBindingError` naming each missing path (mempalace program checked only when `need_mempalace`; `source_path is None` is an error). Never call `shutil.which` (research R1, data-model § McpBinding)
- [X] T008 In `mneme/mempalace/mcpface.py` add pure entry builders `mneme_entry(b) -> dict` (`{"type":"stdio","command":str(b.mneme_program),"args":["mp","mcp","--config",str(b.config_path)]}`, no `env`) and `mempalace_entry(b, store_path) -> dict` (`{"type":"stdio","command":str(b.mempalace_program),"env":{"MEMPALACE_PALACE_PATH":str(store_path),**b.env}}`) per contracts/mcp-face.md (depends on T007)
- [X] T009 In `mneme/mempalace/mcpface.py` add `merge_write(path: Path, entries: dict[str, dict]) -> Path`: if file exists, parse; non-dict JSON or parse error → raise `McpFaceError(path, reason)` without writing; replace only the given keys under `mcpServers`, keep every other key/value and top-level key and existing key order; write `json.dumps(data, indent=2)+"\n"` to a temp file in the same dir then `os.replace` (research R8) (depends on T007)
- [X] T010 [P] Tests in new `tests/unit/test_mcpface.py` for T007–T009: binding from a fake venv in `tmp_path` (create `bin/mneme`, `bin/mempalace-mcp`, a hypostasis.yaml); missing program → error names it; a decoy `mempalace-mcp` first on `PATH` (monkeypatch) is ignored; builders emit exact contract JSON and no secrets (put `OPENAI_API_KEY` in env, assert absent); merge_write preserves foreign keys (`campaign`, `5etools`) and order, is atomic (no temp left), refuses invalid JSON leaving bytes unchanged

**Checkpoint (Opus gate)**: ruff + pytest green; diff read.

---

## Phase 3: User Story 1 — the campaign session can reach its own mneme (P1) 🎯 MVP

**Goal**: `mp faces` / bring-up write a `mneme` entry for OWNED campaigns, even with no store.
**Independent test**: render an OWNED tmp campaign → its `.mcp.json` has the exact `mneme` entry and its other servers untouched; FOREIGN campaign → refused, nothing written.

- [X] T011 [US1] Rework `render_mcp` in `mneme/mempalace/render.py` (~line 386) to `render_mcp(cfg, campaign_dir, binding) -> Path` that calls `mcpface.merge_write` with `{"mneme": mneme_entry(binding)}` plus `{"mempalace": mempalace_entry(binding, cfg.store.path)}` only when `cfg.store` is set (contract rule 3: with no store, leave any existing `mempalace` key alone)
- [X] T012 [US1] Change `render_faces` in `mneme/mempalace/render.py` (~line 410) to take `binding: McpBinding` instead of `env`, always call `render_mcp` (FR-008), keep the global alias inside `if cfg.store is not None`; update both callers in `mneme/mempalace/bringup.py` (lines ~143 and ~192) to build `binding = mcpface.binding_for(entity, need_mempalace=cfg.store is not None)` before any write
- [X] T013 [US1] (REVISED, research R2) Verify — do not add a new gate — that `render_existing_faces` and bring-up refuse FOREIGN campaigns via `discover.resolve()`; was: Add the ownership gate to `render_existing_faces` in `mneme/mempalace/bringup.py` (~line 174): if `ownership.classify(ref.path, entity.mneme_identity)` is not `OWNED`, raise `DiscoveryError(discover.foreign_refusal(entity, ref))` (or the existing unintegrated message) before rendering (research R2); confirm bring-up's existing ownership handling covers the new-campaign path and note it in the task result
- [X] T014 [US1] In `mneme/mempalace/cli.py::faces` (~line 642) also catch `mcpface.McpBindingError` and `mcpface.McpFaceError` → `FAIL faces: …`, exit `EXIT_RUNTIME`
- [X] T015 [P] [US1] Tests in `tests/unit/test_mcpface.py` (render section) and update `tests/unit/test_mp_store_foundation.py::test_mcp_face_points_at_store_no_hardcode` + `tests/integration/test_mp_right_store.py` mcp tests to the new signature/entries: OWNED render writes `mneme` entry with absolute command and `--config <abs>`; existing `campaign` key preserved; no-store campaign gets `mneme` and no `mempalace`; FOREIGN and UNINTEGRATED → refused, file absent/unchanged; secrets never present

**Checkpoint (Opus gate)**: ruff + pytest green. US1 is shippable alone.

---

## Phase 4: User Story 2 — the palace server is pinned to the owning mneme (P1)

**Goal**: the `mempalace` entry's command is `<venv>/bin/mempalace-mcp`, never a bare name.
**Independent test**: decoy on PATH → entry still names the venv program; missing venv program → render fails, neither file changed.

- [X] T016 [US2] Verify T011/T012 already emit the absolute `mempalace` command; ensure bring-up/`mp faces` with a store and a venv lacking `mempalace-mcp` raises `McpBindingError` before ANY face file is written (move `binding_for` ahead of `write_all` in `render_faces` / bringup if needed) in `mneme/mempalace/render.py` and `mneme/mempalace/bringup.py`
- [X] T017 [P] [US2] Tests in `tests/unit/test_mcpface.py`: decoy `mempalace-mcp` first on PATH → entry command is the venv path; venv without `mempalace-mcp` + store → error naming it and every face file (wing yamls, config.yaml, `.mcp.json`) byte-identical to before

**Checkpoint (Opus gate)**.

---

## Phase 5: User Story 3 — status reports a missing or foreign entry (P2)

**Goal**: the `faces` row flags missing/foreign/bare entries with the reasons in contracts/status-rows.md.
**Independent test**: delete `mneme` key → `faces` STALE_RENDER naming it; re-render → conformant.

- [X] T018 [US3] In `mneme/mempalace/mcpface.py` add `file_reasons(path: Path, where: str, binding, store_path: Path | None, env) -> list[str]` producing exactly the reason strings of contracts/status-rows.md (`missing`, `unreadable`, `has no mneme server`, `mneme command != …`, `mneme config != …`, `mempalace command != …`, `mempalace palace != store path`, `embedder/backend env out of date (…)`); mempalace checks only when `store_path` is set
- [X] T019 [US3] Refactor `faces_coherent` in `mneme/mempalace/render.py` (~line 425) to take `binding` (optional; when it cannot be built, add one reason `mcp: cannot bind owning mneme: <error>`), run the existing cli_pointer/global_alias checks only when `cfg.store` is set, and replace its inline mcp block with `mcpface.file_reasons(campaign_dir/".mcp.json", ".mcp.json", …)` so the mneme entry is checked even without a store (research R7)
- [X] T020 [US3] In `mneme/mempalace/conform.py`: move the `faces` row out of `_store_backup_rows` (~line 170) into a new `_faces_row(ref, cfg, entity)` appended in `_campaign_rows` (~line 498) for OWNED campaigns whenever `entity` is set (store or not); build the binding via `mcpface.binding_for(entity, need_mempalace=cfg.store is not None)`; append `— run \`mneme mp faces <name>\`` to the note when stale; keep the `right store everywhere` note when coherent
- [X] T021 [P] [US3] Tests in `tests/unit/test_mp_conform.py`: fresh render → `faces` conformant; delete `mneme` key → STALE_RENDER with `has no mneme server`; bare `mempalace-mcp` (today's render) → `mempalace command != …`; wrong `--config` → `mneme config != …`; invalid JSON → `unreadable`; no-store campaign still gets a `faces` row

**Checkpoint (Opus gate)**.

---

## Phase 6: User Story 4 — the session opened at the clone root loads the face (P2)

**Goal**: single-campaign clone roots get both entries; multi-campaign → to-do; multi + root entries → FAIL with zero writes.
**Independent test**: see quickstart §2 US4 rows and §5.

- [X] T022 [US4] In `mneme/mempalace/mcpface.py` add frozen dataclass `CloneLayout(root: Path | None, campaigns: tuple[str,...], shared_declared: bool, root_has_mneme_entries: bool, verdict: str)` and `clone_layout(ref, entity) -> CloneLayout` implementing data-model.md § Verdict exactly (first-match order: NO_CLONE, CONFLICT [only when shared declared], UNDECLARED, MULTI, SINGLE; campaigns = sorted non-dot, non-symlink child dirs of `ref.tree` not in `entity.campaign_shared_dirs`; a campaign whose own name is in the shared set → UNDECLARED-style verdict with a collision note). Read-only
- [X] T023 [US4] In `mneme/mempalace/render.py::render_faces` (or `render_mcp`) take `layout: CloneLayout | None`; when `layout.verdict == "SINGLE"`, also `merge_write(layout.root/".mcp.json", same entries)`; in every other verdict never open the root file for writing; return written paths. Callers in `mneme/mempalace/bringup.py` compute `mcpface.clone_layout(ref, entity)`; `render_existing_faces` returns `(written, layout)` or the CLI computes the layout itself — pick one and keep it in `bringup.py`
- [X] T024 [US4] In `mneme/mempalace/cli.py::faces` print `skipped <root>/.mcp.json: <reason>` (stdout, exit 0) for verdicts CONFLICT/MULTI/UNDECLARED (contracts/mcp-face.md § `mp faces` output)
- [X] T025 [US4] In `mneme/mempalace/render.py::faces_coherent` / `conform._faces_row`: when verdict is SINGLE also run `mcpface.file_reasons(layout.root/".mcp.json", "root .mcp.json", …)`
- [X] T026 [US4] In `mneme/mempalace/conform.py` add `_clone_row(ref, entity)` appended after `_faces_row` for OWNED campaigns with a clone root: SINGLE → `CONFORMANT` `single-campaign clone <root>`; UNDECLARED / MULTI → `CLONE_ROOT_OWED`; CONFLICT → `CLONE_ROOT_CONFLICT`; notes verbatim from contracts/status-rows.md (CONFLICT note cites kostadis/campaigns#672)
- [X] T027 [P] [US4] Tests in `tests/unit/test_mcpface.py` (layout section) and `tests/unit/test_mp_conform.py` (clone row), using `tmp_path` trees only: single campaign + `[gm-assistant, scripts]` declared → root written, other root keys preserved, clone conformant; two campaigns, no root mneme keys → root untouched, `clone_root_owed`; two campaigns + root `mneme` key → `sha256` of root file identical after render, `clone_root_conflict` FAIL; shared set undeclared → root untouched, `clone_root_owed` listing children; dot-dirs and symlinked dirs not counted; campaign resolved via `--dir` with no tree → no clone row
- [X] T028 [P] [US4] Two-mneme test in `tests/unit/test_mcpface.py`: two fake venvs + two hypostasis configs with different `mneme.id`, two tmp clones each owning one campaign; rendering with config A writes only A's paths into A's campaign and root, and refuses B's campaign (SC-003)

**Checkpoint (Opus gate)**: full suite green; diff read.

---

## Phase 7: Polish, the one review pass, PR

- [X] T029 [P] Update `README.md` (`mp faces` / `mp mcp` lines and the faces description ~line 80–100) to say the mcp face registers `mneme` and `mempalace` pinned to the owning mneme, and document `campaign_shared_dirs` and the clone-root rule; add `campaign_shared_dirs` to the example hypostasis config if the repo ships one (`hypostasis.example.yaml`)
- [X] T030 Run the quickstart §2 scenario table against the test suite and confirm each row maps to a passing test; list any gap and close it (Opus)
- [X] T031 Commit the branch in logical commits (spec docs; hypostasis key; mcpface + render; status; docs), messages ending with the Co-Authored-By line (Opus)
- [X] T032 Run `/code-review` **once** on the branch diff vs `origin/main`. For each finding: fix it (implementer, then re-gate) if it is cheap and in scope, else record it for T035. No second review pass (Opus)
- [ ] T033 Push `008-mcp-face-owning-mneme` and open the PR to `main` via `mcp__github__create_pull_request`, body summarising US1–US4, `Closes #87`, linking kostadis/campaigns#672, ending with the Claude Code attribution line (Opus)

---

## Phase 8: Leftovers → issues, then GM handoff

- [ ] T034 File the known follow-ups as kostadis/mneme issues via `mcp__github__issue_write`: (a) discovery should use `campaign_shared_dirs` so `gm-assistant`/`scripts` stop being reported as campaigns (research R4); (b) the non-mneme campaign servers (`campaign`, `5etools`, `registry`, `provenance`) also resolve via PATH, so name the owning repo/component (Opus)
- [ ] T035 File one issue per unfixed `/code-review` finding from T032 (or one grouped issue if they are small), and link every issue from T034–T035 in a PR comment (Opus)
- [ ] T036 GM handoff (not executed by any agent): after merge + install into `~/.venvs/main`, the GM adds `campaign_shared_dirs: [gm-assistant, scripts]` to `~/.config/hypostasis/hypostasis.yaml`, then runs quickstart §4 (`mp faces` for Phandalin, out-of-the-abyss, obelisk, toee, greenwold; `mp status`; open a session in `~/toee` and call `get_status`)

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → (US1 → US2) → US3 → US4 → Phase 7 → Phase 8.
- US2 has almost no code of its own: it is a verification-and-test phase on top of US1's `render_mcp` change, so it follows US1.
- US3 depends on US1 (the entries it checks). US4 depends on US1 (the render path) and US3 (`file_reasons`, `_faces_row`).
- Within phases, all `[P]` tasks touch different files from their siblings.

## Parallel Opportunities

- Phase 2: T002+T004 (hypostasis) ∥ T005+T006 (State/format) ∥ T007→T008→T009→T010 (mcpface). That's three implementers.
- US1: T015 tests ∥ T014 CLI once T011–T013 land.
- US4: T027 ∥ T028 once T022–T026 land; T029 docs can run any time after US4's design is fixed.

## Implementation Strategy

- **MVP** = Phases 1–3 (US1): every campaign session opened *in the campaign dir* gets a working, correctly-bound `mneme` server.
- US2 closes the PATH defect. US3 makes regressions visible. US4 makes it work where sessions actually open on this host (clone roots). Without US4, SC-005 is unmet on this host, so ship all four in one PR.

## Gate notes


- Phase 1: baseline `uv run --extra dev pytest -q tests/unit tests/integration` → 855 passed, 3 skipped. `ruff check .` → 11 pre-existing errors (backup.py, cli.py:24/657, ownership.py, publish.py, target.py, 3 tests); gate = no NEW ruff errors. Run tooling via `uv run --extra dev` in the worktree (~/.venvs/main has no pytest).
- Phase 2: 874 passed, 3 skipped; ruff 11 (unchanged). Review note: merge_write's mkstemp file is 0600 → os.replace would change .mcp.json perms; fix in US1 (preserve existing mode, else 0644-ish umask default). Untracked uv.lock from `uv run` — do not commit.
- US1+US2: 882 passed, 3 skipped; ruff 10 (B013 fixed). merge_write now preserves mode. Fixtures get a hermetic fake venv + hypostasis.yaml beside the campaigns root. Bring-up with a missing program → configure skipped "nothing written" + first_mine failed.
- US3: 893 passed, 3 skipped; ruff 10. faces row moved to _faces_row (emitted with or without store, not for FOREIGN). Contract gained `has no mempalace server` + `cannot bind owning mneme` + store-less note. test_mp_status now renders faces first (store-less campaign without .mcp.json is a faces FAIL by design, FR-008).
- US4: 907 passed, 3 skipped; ruff 10. Deviation (accepted): clone_layout only treats a DECLARED data_roots.campaigns tree as a clone root (--dir sets ref.tree to the parent). Read-only live status from the worktree: all 5 campaigns faces FAIL with specific reasons (toee no mneme; Phandalin/OotA mneme entry lacks --config; greenwold foreign mneme command; obelisk campaign .mcp.json has no mempalace); all 5 clone_root_owed (shared set undeclared). No files written.
- Phase 7: T029 docs done by Opus directly (README § The mcp face, ~30 lines; too small to brief). T030: all quickstart §2 rows map to tests in test_mcpface.py / test_mp_faces_status.py (UNINTEGRATED row revised per R2).
- Review (one pass): 10 findings. Fixed 1,2,3,4,6,7,8 + rename part of 10 (914 passed, 3 skipped; ruff 10). Kept 5 by GM ruling (any mneme/mempalace entry at a multi-campaign root = FAIL). Deferred 9 + double-ownership part of 10 → issue.
