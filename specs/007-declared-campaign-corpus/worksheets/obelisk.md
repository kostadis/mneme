# Corpus worksheet — obelisk

- Surveyed path: `/home/kostadis/obelisk/obelisk` (git root is the parent, `/home/kostadis/obelisk`)
- HEAD: `f80a2be1` (committed 2026-10-19)
- Date: 2026-10-23 (survey); section 0 added 2026-10-25
- Other copy: `/home/kostadis/src/campaigns/obelisk` also has a `.mneme/`, at older commit `2b34ac79`. It was not surveyed.

Sections 1–7 are observations only. Nothing here is a decision; the GM writes `.mneme/corpus.yaml`. Section 0 is the conversion path, revised with what the Phandalin and out-of-the-abyss migrations taught.

---

## 0. Conversion path and lessons from Phandalin and out-of-the-abyss (2026-10-25)

Phandalin and out-of-the-abyss were both migrated on 2026-10-25, each by integrate + bringup. Both ended with `mneme mp status` all ok and the corpus conformant. This section carries over what those runs taught, plus two things that only obelisk has (0.2). **Nothing here decides obelisk membership.** Earlier answers appear only as precedent, next to a blank for this campaign's answer.

### 0.1 Before you start

- **Pull the checkout.** On 2026-10-25, `~/obelisk` is at `f80a2be1`, **119 commits behind `origin/main`**. None of those commits touch `obelisk/`, so the counts in sections 1–6 still hold.
- **Clean up the untracked files.** `git status` shows 48 untracked entries:
  - 46 under `notes/grounding_delta/ch013/` (the `runs/` subtree, candidates, scripts);
  - `notes/npc_delta/ch013/tailscale_runtime.json`;
  - `.review-runtime/`.
- **Untracked does not mean skipped.** Only *gitignored* files are left out of a declared dir (#65). A probe of `dirs: [notes]` resolves 68 untracked files (0.5). Before bringup, decide whether to commit, gitignore or delete them: ______
- **Host versions** (all true on this host on 2026-10-25):
  - mempalace on `kostadis-dev`, with `--skips-json` (#56) and Ollama sub-batching (mempalace#57 / PR #58). The large files that might be declared are `docs/background/obelisk.md` (620,642 bytes) and `docs/zenvon-forepot-level-3.pdf` (824,098 bytes).
  - mneme at `5831944` or later (#68, the CampaignGenerator face goes to `config/config.yaml`). `mneme mp search` (#74) is optional, but it is the safe way to spot-check the palace afterwards. A bare `mempalace search` uses the wrong embedder (#73).
  - CampaignGenerator at `9d4079a` or later (#594, `canon_wings`). Restart any running CampaignGenerator MCP server or UI after migrating.
- **`data_roots`.** `~/obelisk` is not in `data_roots.campaigns` in `~/.config/hypostasis/hypostasis.yaml`, so `mneme … obelisk` fails with "campaign workspace not found". Out-of-the-abyss added its root and never needed `--dir` again. `mp adopt` (0.2) has **no `--dir` option**, so obelisk needs either the `data_roots` entry or a hand edit. Add `~/obelisk`: ______

### 0.2 What is different about obelisk

Phandalin and out-of-the-abyss had no `.mneme/`. Obelisk already has one, integrated 2026-07-03:
- `owner.yaml`, with mneme id `64cf8b36-…` (this host's id, so `mp status` reports `owner: owned`);
- `mempalace.yaml`, the wing-model authority described in section 1.

That changes the path in three ways.

1. **The recipe has to move to v3.** The authority says `recipe_version: 2.0.0`. Recipe v2 defines no `kinds:`, so once `corpus.yaml` exists, every corpus command refuses with `recipe-no-kinds: recipe v2 defines no kinds; adopt v3 or later (mneme mp adopt)`. `mp status` today shows `recipe divergent_pending  upgrade available, not yet adopted`. Out-of-the-abyss was born on `3.0.0`.
2. **The `wings:` key has to go.** Once `corpus.yaml` exists, `authority.validate` refuses an authority that still has `wings:` (or `extra_exclusions:`): `dual-authority: .mneme/mempalace.yaml has 'wings:' but .mneme/corpus.yaml exists; the corpus file declares the wings, so remove the key`. Without a `corpus.yaml`, an authority with no wings is also refused (`wings: at least one wing is required`). So **removing `wings:` and writing `corpus.yaml` happen together**, before any mneme command runs. Keep `campaign: obelisk` and `store.alias: obelisk`. The authority's `campaign:` must equal `corpus.yaml`'s (rule 1).
3. **There are two ways to make the change.** Pick one: ______
   - **(a) Adopt, then edit.** Run `mneme mp adopt obelisk --here` to preview, then `--confirm`, before `corpus.yaml` exists. That moves `recipe_version` to `3.0.0`, keeps the wings, re-renders the wing-model files, and leaves everything uncommitted. Then delete `wings:` by hand and write `corpus.yaml`. This needs the `data_roots` entry.
   - **(b) Hand edit.** In `.mneme/mempalace.yaml`, set `recipe_version: 3.0.0`, delete the `wings:` block, and write `corpus.yaml`, all in one sitting. Bringup re-renders everything afterwards anyway.

**Bringup or regenerate.** There is no obelisk palace on this host. `~/.mempalace/palaces` holds `chat`, `out_of_the_abyss` and `phandalin`. `mp status` reports `store: not provisioned` and `faces: FAIL stale_render` (no `config.json` palace entry and no `.mcp.json`). The standing decision is "migration is a fresh rebuild (`mp regenerate --confirm`), never in-place conversion". Here both commands build from empty:
- `mp bringup` loads the existing authority (`_plan_config`). It renders all faces, first-mines through the corpus, and takes a backup. That is the step that fixed the faces for the other two campaigns.
- `mp regenerate --confirm` validates the corpus, clears the store (here, nothing), first-mines and records an empty former-wings record. It does **not** render faces. You would still need `mneme mp render obelisk`, then `mneme mp backup obelisk`.

Which one: ______

### 0.3 Steps

These assume `data_roots` has `~/obelisk`; otherwise add `--dir ~/obelisk/obelisk` to each command.

1. Pull, then deal with the untracked files (0.1).
2. Move the recipe and drop `wings:` by path (a) or (b) (0.2), and write `.mneme/corpus.yaml` from section 7. Skip `mneme integrate`, because `owner.yaml` already exists. `mneme corpus init obelisk` writes a blank skeleton if you want one, and refuses if the file already exists.
3. Run `mneme corpus check obelisk` until it reports valid. Spot-check a kind with `mneme corpus toc obelisk --kind <kind> --json`.
4. Run `mneme mp bringup obelisk --verbose` (or regenerate, per 0.2) and **let it run to the end**. The run looks hung on large files, but it is still working. Two lines are normal and need no action:
   - "cannot read sources" before the first mine;
   - `add/upsert with vectors= bypasses the configured embedder` (mempalace#59).
5. **Check the CampaignGenerator face by hand.** Today `config/config.yaml` lines 45–50 read `canon_wing: narrative` and `index_wings: [notes, summaries, obelisk]`. After bringup that block must hold `canon_wings:` and `index_wings:` matching the declared kinds' trust. The rest of the file is preserved. `mp status` does not check this block yet (mneme#69). If it is stale, run `mneme mp render obelisk`.
6. Run `mneme mp status obelisk`. Expect `recipe` conformant, `corpus` conformant, `index` ok, `embedder` 1024-dim, `faces` ok and `owner` owned.
7. If regenerate was used, run `mneme mp backup obelisk`. Bringup takes its own backup.
8. Optionally spot-check with `mneme mp search obelisk "<an NPC name>" --wing npcs`.
9. Commit in the campaigns repo, on a branch, through a PR: `.mneme/mempalace.yaml`, `.mneme/corpus.yaml`, `config/config.yaml` and `.gitignore`, plus the root `mempalace.yaml` and the other derived files, depending on 0.4.

### 0.4 Repo hygiene (checked on this checkout)

- **The `.mneme/` files are already tracked** (`git ls-files` lists `.mneme/mempalace.yaml` and `.mneme/owner.yaml`). Obelisk's `.gitignore` has **no** bare `mempalace.yaml` rule, on purpose: lines 1–5 explain that such a rule "would silently swallow the .mneme authority". So the `!.mneme/mempalace.yaml` exception that Phandalin needed is not needed here.
- `.mneme/corpus.toc.json` is not ignored yet. The corpus render appends its own ignore line, so `.gitignore` shows modified after bringup. Commit that change.
- **The root `mempalace.yaml` is tracked and already mneme-rendered** (`palace: obelisk`, with a source-sha256 stamp). Bringup rewrites it as the corpus root yaml, so git shows it modified. Out-of-the-abyss untracked its own root file, and **pulling that commit deleted the file on disk**, which sent `render` and `faces` to `stale_render` until `mneme mp render` ran. Every host that pulls such a commit needs the same render. Obelisk's `.gitignore` has no rule that would keep an untracked root file out of `git status`. Decide whether to commit the rendered file or untrack it and add a root-anchored `/mempalace.yaml` ignore rule: ______
- The other mneme-rendered files (`.mempalaceignore` and `docs/chapters/`, `notes/` and `summaries/mempalace.yaml`) are wing-model renders. Check after bringup whether the corpus render rewrote, removed or left each one, and commit to match.
- **Palace name.** `campaign: obelisk` matches the folder's capitalization on GitHub, and `store.alias: obelisk` gives `~/.mempalace/palaces/obelisk`. No legacy palace exists to carry over. Confirm the name: ______

### 0.5 How declarations resolve (dry resolve, 2026-10-25)

These probes ran the resolver (recipe 3.0.0) against this checkout in Python, with nothing written to the campaign. **They are not a proposed corpus.** Every probe returned 0 findings; git mode was `work-tree`.

| Probe declaration | Files resolved | Notes |
|---|---|---|
| `files:` `docs/{world_state,campaign_state,planning,party}.md` | 4 `.md` | No symlinks; plain files, unlike out-of-the-abyss. |
| `dirs: [docs/npcs]` | 775 (739 `.md`, 34 `.json`, 2 `.html`) | Includes the 733 `summary_native/` pipeline files. |
| `files:` the 42 top-level `docs/npcs/*.md` | 42 `.md` | The Phandalin / out-of-the-abyss precedent: list the files instead of the dir. |
| `dirs: [docs/summaries]` | 13 `.md` | `.zvec-grep/` is gitignored and skipped. |
| `dirs: [notes]` | 150 (52 `.json`, 50 `.md`, 33 `.txt`, 13 `.py`, 2 `.html`) | By subdir: `grounding_delta` 106, `npc_delta` 22, `session_prep` 10, top level 5, `handouts` 5, `strategy` 2. **68 are untracked** (0.1). |
| `dirs: [notes/session_prep]` | 10 `.md` | |
| `dirs: [notes/handouts]` | 5 `.md` | |
| `dirs: [docs/chapters]` | 3 `.md` | `docs/chapters/mempalace.yaml` is not counted. |
| `dirs: [docs/background]` | 8 (7 `.md`, 1 `.txt`) | Includes the 620 KB `obelisk.md` module text. |
| `dirs: [characters]` | 6 `.md` | `characters/old/` holds 1 file and needs its own decision. |

What carries over:
- **Gitignored means not in the corpus** (#65). Gitignored files under a declared dir are skipped silently. A gitignored path named in `files:` is an error.
- **There is no exclude list inside a declared dir.** To keep `docs/npcs/summary_native/` out, list the wanted files under `files:`, as both earlier campaigns did with their top-level dossiers. Here that would be the 42 top-level `docs/npcs/*.md`: ______
- **A file reachable from two kinds needs `mined_as: true` on exactly one of them.** Both earlier campaigns had `docs/party.md` in `party` and `grounding`, mined as grounding. Here it is the same question (section 4): ______
- **Trust decides which wings are canon.** Kinds with `trust: authoritative` become `canon_wings`, which CampaignGenerator's `grounded_search` verifies against. Kinds with `trust: reference` become `index_wings`. Defaults: `npcs`, `summaries`, `party` and `grounding` are authoritative; `prep` is reference. A campaign kind must state its trust.
- **Campaign kinds, as precedent.**
  - Phandalin: `lore` (authoritative), and `background`, `module` and `prep` (reference).
  - Out-of-the-abyss: `lore` (authoritative) and `module` (reference). Book-length module texts went in a reference kind in both.
  - Here the candidates are `docs/background/` (the module text and inventories), `characters/` and `voice/` (PC data, section 2 "party"), `notes/strategy/` and the tracking files under `docs/` (section 6): ______
- **Both earlier campaigns left `docs/chapters` out.** Here `docs/chapters/` (3 `.md`) is today's only `trust: authoritative` wing (`narrative`), so leaving it out removes CampaignGenerator's canon wing until the new kinds replace it. In or out: ______
- **Out-of-the-abyss's `prep` was a list of `notes/` subdirs**, not all of `notes/`. It left out every pipeline dir (`npc_delta`, `summary_native`, `ensemble*`, `reviews`, `authority`, …). The obelisk equivalents are `notes/grounding_delta`, `notes/npc_delta`, `docs/summary_native`, `docs/npcs/summary_native`, `docs/archive`, `docs/reviews` and `docs/authority`: ______
- **Summaries.** Both earlier campaigns declared only `docs/summaries` and left the pipeline `summaries/*/session-summary.md` out. Obelisk's current `summaries` wing points at the **pipeline** `summaries/` (1078 files); `docs/summaries/` (13) has no wing today. Which one: ______
- **The PDF.** `docs/zenvon-forepot-level-3.pdf` is the only PDF. If it is declared, check after the mine whether mempalace skipped it; `mp status` `gaps` lists every skip.
- **`arcs` is Phandalin-only.** It feeds CampaignGenerator's `arc_triggers`. Obelisk has `docs/oblesik_tracking.md`, but no `docs/tracking/`.

---

Counts are files (`find <dir> -type f`) unless stated. Counts that include tool-state dirs (`.zvec-grep/`, `.tgrep/`) are noted.

## 1. What the palace mines today

Source: `.mneme/mempalace.yaml` (`recipe_version: 2.0.0`, `store.alias: obelisk`). No `extra_exclusions:` key is present.

| wing | source | trust | note |
|---|---|---|---|
| `narrative` | `docs/chapters` | authoritative | drops out of the palace unless declared |
| `notes` | `notes` | reference | |
| `summaries` | `summaries` | reference | source `summaries` is the top-level pipeline output, not `docs/summaries` |
| `obelisk` | `.` | reference | whole campaign root |

Other facts:
- `.mempalaceignore` (mneme-rendered) lists: `logs/ voice/ examples/ .claude/ .mneme/ .mcp.json MEMPALACE.md *.sh config.yaml ui_config.yaml ui_state.yaml entities.json refs.yaml refs.local.yaml .dedup_state.json docs/chapters/ notes/ summaries/`.
- Other `mempalace.yaml` files: `mempalace.yaml` (root), `docs/chapters/mempalace.yaml`, `notes/mempalace.yaml`, `summaries/mempalace.yaml`.

Palace contents not surveyed: no read-only source listing exists until T005.

## 2. Files at each standard kind's usual locations

### npcs
- `docs/npcs/` total: 775 files
  - top level: 42 files (all `.md`)
  - `docs/npcs/summary_native/`: 733 files
    - `ch001-012/`: 685
    - `ch001-013/`: 32
    - `ch013-013/`: 15
    - `publish_log.json`: 1
  - `docs/npcs/distilled/`: absent
  - `docs/npcs/authored/`: absent
- Reproduce: `find docs/npcs -type f | wc -l`

### summaries
- `docs/summaries/` (published): 13 `.md` files, `001-session-phandalin-the-threshold-awaits.md` ... `013-session-untitled.md`, plus a tool-state dir `docs/summaries/.zvec-grep/` (100 files; 113 total).
- `summaries/` (pipeline output): 1078 files in total, including tool-state dirs.
  - Top-level entries: `001 002 003 004 005 006 007 008 009 010-20260821 011-20260904 012-202610-09 013-20261018 mempalace.yaml`, plus `.zvec-grep/`, `.tgrep/`.
  - Files per session dir: 001=82, 002=110, 003=70, 004=2, 005=25, 006=54, 007=53, 008=142, 009=51, 010-20260821=100, 011-20260904=162, 012-202610-09=49, 013-20261018=79.
  - `.md` files outside tool-state dirs: 466. Other extensions found under `summaries/`: json 286, vtt 41, yaml 54, html 50, log 38, txt 17, diff 14, patch 9, m4a 5, sst 19, and store-internal files.
  - Subdir names seen inside session dirs (count of session dirs holding each): `logs` 12, `scene_extractions_smoothed` 8, `scene_extractions_new` 6, `narration` 5, `scene_extractions` 4, `spell_review` 2, `staged_review` 2, and one each of `batch_review`, `dialogue_edit`, `narration_dgx`, `narration_prompt_test`, `narration_test_nomech`, `speaker_attribution_text`, `speaker_review`, `voice_critic`, `voice_smooth_calibration`, `voice_smooth_previous_20260910`, `.cg`, `.agents`, `.codex`, `.git`.
- Reproduce: `find summaries -type f | wc -l`; `ls summaries`

### grounding
- `docs/world_state.md`: present
- `docs/campaign_state.md`: present
- `docs/party.md`: present
- `docs/planning.md`: present

### party
- `docs/party.md`: present (also a grounding doc, see section 4)
- `docs/party/`: absent
- `docs/party_state.md`: absent
- `*_backstory*` anywhere in the campaign (excluding `.git`): none found
- Per-character files elsewhere: `characters/` (6 entries: `Zenvon Forepot.md`, `maela.md`, `pip.md`, `sidekick_progressions.md`, `veyra.md`, and dir `old/` with 1 file); `voice/` (7 files); `config/party.yaml`, `config/players.yaml`

### prep
- `notes/sessions/`: absent
- `notes/` total: top-level entries and file counts:
  - `notes/grounding_delta/`: 111
  - `notes/handouts/`: 11
  - `notes/npc_delta/`: 26
  - `notes/session_prep/`: 106 (includes tool-state dirs)
  - `notes/strategy/`: 97 (includes tool-state dirs)
  - `notes/mempalace.yaml`, `notes/scrub_register_policy.md`, `notes/vtt_known_additions.md`, `notes/vtt_transcription_corrections.md`: 1 each
- `notes/session_prep/` direct files include: `20260904_chapter_10_the_wizard_of_the_old_owl_well.md`, `20260907_chapter_11_look_who_came_to_dinner.md`, `20261015_chapter_12.md`, `cragmaw_castle.md`, `redbrand_hideout.md`, `open.md`, and others.
- `notes/handouts/`: `20261015-veyra-log.md`, `20261025-zenvon-log.md`, `player_quest_log.md`, `player_quest_log_pip.md`, `quest_log.md`
- Reproduce: `find notes -maxdepth 1 -mindepth 1`; `find notes/<dir> -type f | wc -l`

## 3. Look-alikes to decide on

Drafts / candidates / backups:
- `docs/entity_registry.yaml.bak`
- `docs/archive/ensemble/campaign_state_draft.md`
- `docs/archive/ensemble/campaign_state_draft.v2.md`
- `docs/archive/ensemble/world_state_draft.claude.md`
- `docs/archive/ensemble/world_state_draft.spark.md`
- `docs/archive/ensemble/world_state_draft.v2.md`
- `docs/archive/ensemble/world_state_draft.v2.spark.md`
- `docs/archive/ensemble/planning_draft.md`
- `docs/archive/ensemble/planning_draft.v2.md`
- `docs/archive/ensemble/party_draft.md`
- `docs/archive/ensemble/party_draft.v2.md`
- `notes/grounding_delta/ch013/verify_drafts.py`
- `notes/grounding_delta/ch013/runs/pre-revision/campaign_state.candidate.md`
- `notes/grounding_delta/ch013/runs/pre-revision/world_state.candidate.md`
- `notes/grounding_delta/ch013/runs/pre-revision/planning.candidate.md`
- `notes/grounding_delta/ch013/runs/pre-revision/party.candidate.md`
- `notes/grounding_delta/ch013/campaign_state.line_repair_candidate.md` (matches neither pattern exactly; listed by name)

Staging / extraction / review dirs:
- `docs/archive/` (134 files; sole child `ensemble/`, which holds `state_dossiers/`, `merged_dossiers/`, `aliases.json`, `known_names.md`, `plan.yaml`)
- `docs/reviews/` (1155 files; `campaign.json`, `npc-review-*` dirs)
- `docs/summary_native/` (309 files; `ch001-012` 274, `ch013-013` 35)
- `docs/npcs/summary_native/` (733 files)
- `docs/authority/` (2543 files; `events` 29, `snapshots` 2476, `transactions` 37)
- `notes/grounding_delta/` (111), `notes/npc_delta/` (26)
- Not found under `docs/` or `notes/`: `*_extractions/`, `state_staging/`

Reproduce: `find docs notes \( -iname '*_draft*' -o -iname '*.candidate.*' -o -name '*.bak' -o -name '*.old' -o -name '*_extractions' -o -name state_staging -o -name reviews -o -name summary_native -o -name archive -o -name ensemble \)`

## 4. Files that would be shared across kinds

- `docs/party.md`: grounding doc and party data; needs a `mined_as` choice: ______
- `docs/campaign_state.md`, `docs/world_state.md`, `docs/planning.md`: no second kind observed at the usual locations; GM to confirm.
- `docs/summaries/` vs `summaries/`: different directories with different content; no shared files observed.
- `docs/npcs/summary_native/` sits under a standard-kind dir and shares the name of `docs/summary_native/`; observation only.

## 5. Hazards

- Symlinks (`find docs notes summaries voice characters -type l`): none found.
- Gitignored paths (`git check-ignore`): 502 files under `docs notes summaries` are ignored. Patterns observed include tool-state dirs `docs/.zvec-grep/`, `docs/summaries/.zvec-grep/`, `docs/background/.zvec-grep/`, `docs/background/.tgrep/`, `notes/session_prep/.zvec-grep/`, `notes/strategy/.tgrep/`; `docs/.triage_queue.json`; `docs/.entity_triage_state.json`; `docs/authority/.lock`; `docs/background/.module_inventory/`; `*.m4a`, `*.mp3`, `*.wav`; `summaries/*/session-nar.tar`; `summaries/*/.cg/`. Reproduce: `find docs notes summaries -type f | git check-ignore --stdin`
- Skip-worktree / sparse (`git ls-files -t`): 0 entries with `S`; all 6143 tracked files show `H`.
- Nested git: `summaries/002/.git` (also `summaries/002/.agents`, `summaries/002/.codex`).
- Non-text extensions under `docs notes summaries`: `docs/zenvon-forepot-level-3.pdf`; 5 `.m4a` files under `summaries/` (gitignored); `.tar` none found. Binary store files (`.sst`, `.bin`, `.zvec`, `rocksdb/*`) inside `.zvec-grep/` and `.tgrep/` dirs.
- `__pycache__/` exists at the campaign root.

## 6. Candidate campaign kinds

Directories holding material outside the five standard kinds (path and count only):
- `docs/chapters/`: 4 files (`mempalace.yaml`, `session_002_welcome_to_phandalin.md`, `session_003_cragmaw_cave.md`, `session_004_cragmaw_hideout.md`); source of the `narrative` wing
- `docs/background/`: 8 files outside tool-state (`monsters_cr_reference.md`, `monsters_phase1_scan.md`, `monsters_phase2_descriptions.md`, `monsters_phase3_hierarchy.md`, `name_glossary.md`, `obelisk-inventory.md`, `obelisk-inventory.txt`, `obelisk.md`)
- `voice/`: 7 files
- `characters/`: 6 entries (+1 file in `old/`)
- `config/`: 8 files
- `examples/`: 2 files
- `docs/authority/`: 2543 files
- Tracking / reference files directly under `docs/`: `aliases.json`, `authority.yaml`, `corrections.yaml`, `entity_inventory.md`, `entity_registry.yaml`, `mechanics.md`, `oblesik_tracking.md`, `recent_events.md`
- `notes/handouts/`: 11; `notes/strategy/`: 97; `notes/session_prep/`: 106
- Other root entries: `RENUMBERING.md`, `MEMPALACE.md`, `logs/`, `tests/` (0 files), `.review-runtime/`

## 7. GM decisions (2026-10-25)

Every choice below is an explicit GM answer, given in four question rounds on 2026-10-25. `mneme corpus check obelisk` reports the resulting `.mneme/corpus.yaml` valid with 0 findings: 105 distinct paths (`docs/party.md` is in two kinds).

| Kind | Trust | Files | Decision |
|---|---|---|---|
| `npcs` | authoritative | 42 | Only the top-level `docs/npcs/*.md`, listed under `files:`. Out: `docs/npcs/summary_native/` (733). |
| `summaries` | authoritative | 13 | `dirs: [docs/summaries]` only. Out: the pipeline `summaries/` (1078), which today's `summaries` wing mines. |
| `party` | authoritative | 14 | `dirs: [characters, voice]` (`characters/old/` and the 3 `voice/*.proposed.md` included) plus `docs/party.md`, which is mined as grounding. |
| `grounding` | authoritative | 4 | `docs/{world_state,campaign_state,party,planning}.md`; `mined_as: true`. |
| `prep` | reference | 18 | `dirs: [notes/session_prep, notes/handouts, notes/strategy]`. Out: `notes/grounding_delta`, `notes/npc_delta` and the top-level `notes/*.md`. |
| `chapters` (campaign kind) | reference | 3 `.md` | `dirs: [docs/chapters]`. Unlike Phandalin and out-of-the-abyss, the chapters stay in, but at `reference`, so today's `narrative` canon wing goes away. The TOC also lists `docs/chapters/mempalace.yaml` as `minable: false`. |
| `module` (campaign kind) | reference | 11 | `dirs: [docs/background]` plus `docs/{oblesik_tracking,mechanics,entity_inventory}.md`. |

Also decided:
- **Untracked files (0.1):** commit them all: `notes/grounding_delta/ch013/` (46), `notes/npc_delta/ch013/tailscale_runtime.json`, `.review-runtime/`, and the new `notes/session_prep/20261025_chapter_13.md` that appeared after the pull. Only the last one is in the corpus.
- **`data_roots`:** `~/obelisk` added to `data_roots.campaigns`.
- **Recipe path (0.2):** (b) hand edit: `recipe_version: 3.0.0`, `wings:` deleted, `corpus.yaml` written in one sitting.
- **Build:** `mneme mp bringup obelisk`.
- **Left out:** `docs/zenvon-forepot-level-3.pdf`, `docs/{aliases.json,authority.yaml,corrections.yaml,entity_registry.yaml,recent_events.md}`, `docs/archive`, `docs/reviews`, `docs/summary_native`, `docs/authority`, `config/`, `examples/`.
- **Root `mempalace.yaml`:** stays tracked; the bringup rewrite is committed.
- **Palace name:** `obelisk` (`store.alias: obelisk`). Standard kinds keep their default trust.
- Canon wings: `npcs`, `summaries`, `party`, `grounding`. Index wings: `prep`, `chapters`, `module`.

The `corpus.yaml` as written to `obelisk/.mneme/corpus.yaml`:

```yaml
campaign: obelisk
kinds:
  npcs:
    files:
    - docs/npcs/agatha.md
    - docs/npcs/ander.md
    - docs/npcs/brakka.md
    - docs/npcs/brughor-axe-biter.md
    - docs/npcs/daran-edermath.md
    - docs/npcs/dosa-rook.md
    - docs/npcs/droop.md
    - docs/npcs/elmina-barthen.md
    - docs/npcs/elsa.md
    - docs/npcs/freda.md
    - docs/npcs/gog.md
    - docs/npcs/gorl.md
    - docs/npcs/greska.md
    - docs/npcs/gundren-rockseeker.md
    - docs/npcs/halia-thornton.md
    - docs/npcs/hamun-kost.md
    - docs/npcs/harbin-wester.md
    - docs/npcs/hul.md
    - docs/npcs/iarno-glasstaff-albrek.md
    - docs/npcs/king-grol.md
    - docs/npcs/klarg.md
    - docs/npcs/lanar.md
    - docs/npcs/lhupo.md
    - docs/npcs/linene-graywind.md
    - docs/npcs/mirna-dendrar.md
    - docs/npcs/nars-dendrar.md
    - docs/npcs/narth.md
    - docs/npcs/nezznar-the-spider.md
    - docs/npcs/nilsa-dendrar.md
    - docs/npcs/nosk.md
    - docs/npcs/orryn-voss.md
    - docs/npcs/redbrand-ruffian.md
    - docs/npcs/rondar.md
    - docs/npcs/sildar-hallwinter.md
    - docs/npcs/sister-garaele.md
    - docs/npcs/ssarnak.md
    - docs/npcs/thistle.md
    - docs/npcs/toblen-stonehill.md
    - docs/npcs/tuck-stonehill.md
    - docs/npcs/warden-holl.md
    - docs/npcs/wick.md
    - docs/npcs/yeemik.md
  summaries:
    dirs:
    - docs/summaries
  party:
    dirs:
    - characters
    - voice
    files:
    - docs/party.md
  grounding:
    files:
    - docs/world_state.md
    - docs/campaign_state.md
    - docs/party.md
    - docs/planning.md
    mined_as: true
  prep:
    dirs:
    - notes/session_prep
    - notes/handouts
    - notes/strategy
campaign_kinds:
  chapters:
    dirs:
    - docs/chapters
    trust: reference
  module:
    dirs:
    - docs/background
    files:
    - docs/oblesik_tracking.md
    - docs/mechanics.md
    - docs/entity_inventory.md
    trust: reference
```
