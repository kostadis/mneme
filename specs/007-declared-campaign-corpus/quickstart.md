# Quickstart: validating the declared corpus

Validation scenarios that prove the feature end to end. Schemas: `contracts/`. States:
`data-model.md`.

## Prerequisites

- mempalace on `kostadis-dev` with the three CLI additions
  (`contracts/mempalace-cli-additions.md`), and the hypostasis pin bumped to that commit.
- `pip install -e '.[dev]'` in the mneme venv; `pytest` and `ruff` green.
- Slow lane: `MNEME_REAL_MEMPALACE_VENV=<venv>` for `tests/integration/test_real_mempalace_e2e.py`.

## Scenario 1: the palace holds exactly the corpus (US1, SC-001/002)

1. Fixture campaign, in a git repo:
   - `docs/npcs/a.md`, `docs/summaries/001.md`, the four grounding files
   - decoys: `docs/campaign_state_draft.md`, `docs/party_draft.md`, `docs/reviews/x.md`, `summaries/raw.md`
2. Write `.mneme/corpus.yaml` declaring `npcs`, `summaries` and `grounding` only.
3. `mneme mp render C` then `mneme mp refresh C`.
4. **Expect**: `mempalace --palace P sources --json` lists exactly the six declared files.
   The wings are `npcs`, `summaries` and `grounding`. No decoy appears.
5. Add `docs/new_generated/y.md`, then refresh. **Expect**: `sources` is unchanged.

## Scenario 2: status proves it, and never lies (US2, SC-003/004)

Using the palace from Scenario 1, set up each condition and run `mneme mp status C`.

| Setup | Expected `corpus` finding |
|---|---|
| Mine a decoy into the palace with a plain `mempalace mine` | `undeclared-drawers: 1`, remedy `mp prune` |
| Declare `docs/npcs/b.md` without mining it | `unmined: 1`, remedy `mp refresh` |
| Edit `docs/world_state.md` after mining | `stale: 1`, remedy `mp refresh` |
| Declare `docs/gone.md` (untracked, absent) | `missing: 1`, remedy: edit `corpus.yaml` |
| Make the store unreadable (stub returns non-zero for `sources`) | `UNKNOWN`, never `OK` |
| Edit `corpus.yaml` without re-rendering | `toc-stale`, remedy `mp render` |

## Scenario 3: prune removes exactly what was previewed (FR-018)

1. From the "undeclared" setup, run `mneme mp prune C`. **Expect**: a preview listing the
   decoy, with `N` drawers.
2. Run `mneme mp prune C --confirm --expect N`. **Expect**: a backup is taken, `forget`
   applies, a re-verify shows no `undeclared-drawers`, and declared drawers are untouched.
3. Sparse case: mark a declared file skip-worktree (`git update-index --skip-worktree` and
   remove it from the working tree). **Expect**: it is listed under `not_materialized` in the
   TOC, it is not in the prune set, and its drawers survive.

## Scenario 4: consumers read one list (US3, SC-008)

1. `mneme corpus toc C --kind grounding --json`. In the MCP server, call
   `corpus_files(C, "grounding")`. **Expect**: the same file list.
2. Add `docs/npcs/new.md` and ask for `npcs` again, with no render. **Expect**: both
   readers include it immediately.
3. Hand-edit `.mneme/corpus.toc.json`'s file list. **Expect**: both readers are unaffected;
   `mp status` reports `toc-stale` with remedy `mp render`.
4. Break `corpus.yaml` (an unknown kind). **Expect**: both readers refuse with the finding.
5. Ask for an undeclared kind. **Expect**: "not declared for this campaign", not `[]`.

## Scenario 5: validation catches the edge cases (Edge Cases, FR-003a)

`mneme corpus check C` exits non-zero with one named finding for each of these:
- `kinds: {sumaries: …}`
- `campaign_kinds: {npcs: …}`
- a campaign kind without `trust`
- `docs/party.md` under `party` and `grounding` with no `mined_as`
- a symlinked declared file
- a gitignored declared file
- `wings:` left in `.mneme/mempalace.yaml`

## Scenario 6: migration on the live fleet (US4, SC-003/007)

Per campaign (obelisk, toee, out-of-the-abyss):

1. `mneme mp status`. **Expect**: `corpus: undeclared (owed)`. Mining keeps working.
2. `mneme corpus current <c>`. **Expect**: today's mined files, grouped by wing. For toee this
   includes `docs/campaign_state_draft.md` and `docs/party_draft.md` under the root wing.
3. The GM writes `corpus.yaml` (`mneme corpus init` gives the skeleton). No file is moved.
4. `mp render` then `mp status`. **Expect**: the old palace's extra drawers show as
   `undeclared-drawers`, with a prune remedy. Nothing has been deleted.
5. The GM previews and confirms `mp prune`, then runs `mp refresh`. **Expect**: `corpus: OK`.

## Scenario 7: consumer compliance is visible (US5, SC-006)

With the GM-reviewed `mneme/recipes/consumers.yaml`, `mneme corpus consumers --noncompliant`
lists every `independent` consumer, and `mp status` shows the count as owed work.
