# Corpus worksheet — out-of-the-abyss

- Surveyed path: `/home/kostadis/out-of-the-abyss/out-of-the-abyss` (git root is its parent, `/home/kostadis/out-of-the-abyss`; `git rev-parse --show-prefix` = `out-of-the-abyss/`)
- HEAD: `141e2fa8` (2026-10-22 18:48:36 -0700)
- Date: 2026-10-23 (survey); section 0 and the updates in sections 1, 4, 5 and 7 added 2026-10-25
- Other copy: `/home/kostadis/src/campaigns/out-of-the-abyss` exists. It has **no** `.mneme/` directory and so no `.mneme/mempalace.yaml`. It was not surveyed.

Sections 1–6 are observations only. Nothing here is a decision; the GM writes `.mneme/corpus.yaml`. Section 0 is the conversion path, revised with what the Phandalin migration taught.

Sparse-checkout state: the parent repo's `core.sparseCheckout` is true and its patterns include `/out-of-the-abyss/`. `git ls-files -t` run from the surveyed directory shows 26457 entries, all `H`, and none `S`. Across the whole parent repo it shows 26532 `H` and 28968 `S`.

Counting convention: counts are `find <path> -type f` unless stated. Symlinked directories are not followed unless noted.

---

## 0. Conversion path and lessons from Phandalin (2026-10-25)

Phandalin was the first campaign migrated (integrate + bringup on 2026-10-25, `mneme mp status`: corpus conformant). This section carries over what that run taught. **Nothing here decides out-of-the-abyss membership.** Phandalin's answers appear only as precedent next to a blank for this campaign's answer.

### 0.1 Before you start

- **Pull the checkout.** `~/out-of-the-abyss` is at `141e2fa8`, **21 commits behind `origin/main`** (checked 2026-10-25). It also has uncommitted edits to `docs/gauntlgrym/gauntlgrym_bruenor_scene_script.md`, `docs/gauntlgrym/gauntlgrym_faction_pitches.md` and `notes/session_prep/20261018_chapter_72_the_fixed_point_theory_of_fate_review.md`, plus 26 untracked files under `summaries/2026-10-05-chapter_71` and `summaries/2026-10-19-chapter_73`. The bringup mines what is on disk, so commit or stash, then pull. The counts in sections 1–6 are from `141e2fa8`.
- **Host versions** (all true on this host on 2026-10-25):
  - mempalace on `kostadis-dev` at `d23d6a7` or later. This includes `--skips-json` (#56) and the Ollama sub-batching fix (mempalace#57 / PR #58). Without #58 a large file can crash the Windows Ollama runner mid-mine (`dial tcp 127.0.0.1:<port> … actively refused it`). This campaign has two ~1 MB files that may be declared: `docs/TheUnderdark.md` (1,080,062 bytes) and `docs/authority.yaml` (1,165,205 bytes).
  - mneme at `5831944` or later (#68). Before that, the CampaignGenerator face was written to `<campaign>/config.yaml`, which CampaignGenerator never reads.
  - CampaignGenerator at `9d4079a` or later (#594, `canon_wings`). Restart any running CampaignGenerator MCP server or UI after migrating.

### 0.2 Steps

**Use `--dir`.** This host's `data_roots.campaigns` lists only `~/phandalin`, so `mneme … out-of-the-abyss` by name fails with "campaign workspace not found". Every command below takes `--dir ~/out-of-the-abyss/out-of-the-abyss` (or add `~/out-of-the-abyss` to `data_roots.campaigns` in `hypostasis.yaml`).

This campaign has no `.mneme/` (in either `~/out-of-the-abyss` or `~/src/campaigns/out-of-the-abyss`) and no palace on this host (`~/.mempalace/palaces` holds only `chat` and `phandalin`). So, like Phandalin, it is a **bring-up, not a regenerate**: `mp regenerate` needs an existing `.mneme/mempalace.yaml` and refuses.

1. `mneme integrate out-of-the-abyss` writes `.mneme/owner.yaml`. Bringup does not.
2. Write `.mneme/corpus.yaml` from section 7.
3. Run `mneme corpus check out-of-the-abyss` until it reports valid. Then spot-check a kind with `mneme corpus toc out-of-the-abyss --kind <kind> --json`.
4. Run `mneme mp bringup out-of-the-abyss --verbose` and **let it run to the end**. On Phandalin (331 files, 3 large module books) it took long enough that it looked hung, but it was still running. Two lines are normal and need no action:
   - a "cannot read sources" line before the first mine (the palace is still empty);
   - `add/upsert with vectors= bypasses the configured embedder` (turbovecdb logs this when the miner hands it precomputed vectors).
5. **Check the CampaignGenerator face by hand.** `config/config.yaml` must end with a `mempalace:` block holding `canon_wings:` and `index_wings:`. Today that block is `canon_wing: narrative` and `index_wings: [chronicle, abyss]`, and it is replaced. The rest of the file is preserved byte for byte (#68). `mneme mp status` does not check this block yet (mneme#69), so look at it yourself. If it is missing or stale, run `mneme mp render out-of-the-abyss`.
6. `mneme mp status out-of-the-abyss`. Expect `corpus: conformant` ("palace equals the declared corpus; every drawer is current"), `index`, `embedder` (1024-dim), `faces` and `owner` ok.
7. `mneme mp backup out-of-the-abyss`. Status reports `no backup` until you do.
8. Commit in the campaigns repo, on a branch, through a PR: `.mneme/owner.yaml`, `.mneme/corpus.yaml`, `.mneme/mempalace.yaml`, `config/config.yaml`, `.gitignore`, plus the root `mempalace.yaml` if you decide to keep tracking it (0.3).

### 0.3 Repo hygiene (checked on this checkout)

- `.mneme/mempalace.yaml`: the bare `mempalace.yaml` ignore rule would swallow it. This campaign's `.gitignore` already has the `!.mneme/mempalace.yaml` exception; `git check-ignore -v` confirms it. Phandalin lacked the exception, and it had to be added at commit time.
- `.mneme/corpus.toc.json` is not ignored yet. The corpus render appends the ignore line itself, so `.gitignore` shows as modified after bringup; commit that change.
- **The root `mempalace.yaml` is tracked here.** It is the legacy room config (`palace: abyss`, `wing: abyss`, no mneme stamp). The corpus render **overwrites it unconditionally** with a stamped corpus root yaml, so after bringup git shows it modified. (Phandalin's root file was gitignored, so this did not come up there.) obelisk tracks both its root file and `.mneme/mempalace.yaml`. Decide: commit the rendered file / untrack it: ______
- The tracked `.mempalaceignore` files (root, `summaries/`, `notes/`) are hand-written and unstamped. mneme leaves them in place. They have no effect on a corpus campaign, because mining uses `--files-from`.
- **Palace name.** `campaign: out-of-the-abyss` (the folder's capitalization on GitHub) gives the palace `~/.mempalace/palaces/out-of-the-abyss`, not the legacy `abyss`. No `abyss` palace exists on this host, so there is nothing to carry over. Confirm the name: ______

### 0.4 How declarations resolve (dry resolve, 2026-10-25)

These are probes of the resolver against this checkout, run in Python with nothing written to the campaign. **They are not a proposed corpus.** Every probe returned no findings.

| Probe declaration | Files resolved | Notes |
|---|---|---|
| `files:` `docs/{world_state,campaign_state,planning,canon_events_timeline,party}.md` + `dirs: [docs/reference]` | 13 (all `.md`) | Exactly the live grounding generation. The symlinks resolve to their targets, and the symlinked `docs/reference` dir is followed. |
| `dirs: [docs/grounding]` | 132 (105 `.md`, 26 `.json`, 1 `.yaml`) | Every generation (`ch071`, `ch072`, `legacy-…`), plus manifests and staging. |
| `dirs: [docs/npcs]` | 2298 (2180 `.md`, 109 `.json`, 4 `.yaml`, 4 `.html`, 1 `.py`) | Includes the 2198 `summary_native/` pipeline files (drafts, runs, evidence). |
| `dirs: [docs/summaries]` | 69 (all `.md`) | The published summaries only. |
| `dirs: [notes]` | 523 (368 `.md`, 134 `.json`, …) | Under the #65 rule, 15 gitignored files (`.tgrep/` etc.) are skipped. |
| `dirs: [docs/chapters]` | 62 (all `.md`) | `.tgrep/` is gitignored and skipped. |

What carries over from Phandalin:
- **Gitignored means not in the corpus** (mneme#64 / PR #65, merged). Gitignored files under a declared dir are skipped silently. A gitignored path named in `files:` is still an error.
- **There is no exclude list inside a declared dir.** To leave out a subtree such as `docs/npcs/summary_native/`, list the files you want under `files:`. Phandalin listed its 100 top-level dossiers this way. The precedent here would be the 96 top-level `docs/npcs/*.md`, plus a decision on `docs/npcs/authored/` (4 `.yaml`): ______
- **Symlinks** are mined as their targets. When `docs/grounding/current` is re-pointed at a new generation, `mp refresh` replaces the drawers (GM decision 2026-10-24). Declare the stable symlink paths, not a generation path.
- **A file reachable from two kinds needs `mined_as: true` on exactly one of them.** Phandalin: `docs/party.md` is in `party` and `grounding`, mined as grounding. The candidates here are `docs/party.md` and `docs/reference/party.md` (section 4).
- **Trust decides which wings are canon.** Kinds with `trust: authoritative` become `canon_wings`, which CampaignGenerator's `grounded_search` verifies against. Kinds with `trust: reference` become `index_wings`. Defaults: `npcs`, `summaries`, `party` and `grounding` are authoritative; `prep` is reference. A campaign kind must state its trust.
- **Phandalin's campaign kinds, as precedent:** `lore` (authoritative), and `background`, `module` and `prep` (reference). Its rule: "lore is authoritative, everything else is superseded by events". Its book-length module texts went in a reference kind.
- **Phandalin left `docs/chapters` out** ("should not end up in the mempalace"). Here `docs/chapters/` (62 `.md`) is today's `canon_wing: narrative`. Decide whether it is in: ______
- **`arcs` is Phandalin-only.** It feeds CampaignGenerator's `arc_triggers` (Phandalin's arc mechanic). This campaign does not need it. `docs/tracking/` here is 3 `.txt` files.
- Phandalin's `docs/summaries/` files were replicas of `summaries/*/session-summary.md`, and only `docs/summaries` was declared. Here `docs/summaries/` has 69 files; `summaries/` has 74 `session-summary.md`.

---


## 1. What the palace mines today

- This checkout has **no** `.mneme/mempalace.yaml` (`ls .mneme` fails: no such directory).
- `/home/kostadis/src/campaigns/out-of-the-abyss` has no `.mneme/mempalace.yaml` either, so there are no wings, sources or trust values to quote.
- Legacy files that do exist in this checkout root:
  - `mempalace.yaml` is the legacy mempalace room config: `palace: abyss`, `wing: abyss`, rooms `npcs`, `world`, `arcs`, `mechanics`, `dead`, `general`. It is a single wing with keyword-routed rooms, with no `source` or `trust` fields. `.gitignore` lists a bare `mempalace.yaml` rule.
  - `.mempalaceignore` (root) excludes: `docs/chapters/`, `docs/distill/distill_extractions/`, `docs/distill/planning_extractions/`, `docs/distill/campaign_state_extracts/`, `docs/distill/party_extract/`, `docs/distill/party_extractions/`, `docs/ensemble/per_chapter/`, `docs/ensemble/state_dossiers/`, `docs/ensemble/*.json`, `docs/ensemble/cleanup_worklist.md`.
  - `summaries/.mempalaceignore` and `notes/.mempalaceignore` exist. The summaries one lists `*.vtt`, `vtt.cleaned.md`, `vtt.md`, `logs/`, `.cg/`, `*.log`, `*.db` and others. The notes one lists `*.py`, `*.json`, `*.db`, `*.txt`, `.gitkeep`, `vtt_known_additions.md`, `vtt_transcription_corrections.md` and others.
  - `MEMPALACE.md`, `MEMPALACE_HORIZON.md`
- No `trust: authoritative` wings are declared anywhere, so the "drops out of the palace unless declared" flag has nothing to attach to.

**Palace contents:** there is no palace for this campaign on this host (`~/.mempalace/palaces` holds `chat` and `phandalin`; `~/.mempalace/config.json` registers only those two), so there is nothing to list. Checked 2026-10-25.

---

## 2. Files at each standard kind's usual locations

### npcs — `docs/npcs/`

Total files: 2298.

| Location | Files | Notes |
|---|---|---|
| `docs/npcs/*.md` (direct children) | 96 | all `.md` |
| `docs/npcs/authored/` | 4 | `pizwog.authored.yaml`, `tadric.authored.yaml`, `sylvira-savikas.authored.yaml`, `brysis-of-khaem.authored.yaml` |
| `docs/npcs/summary_native/` | 2198 | 1 direct file (`publish_log.json`); the rest are in `ch002-071/` (1499), `ch002-072/` (657), `ch002-073/` (32), `ch073-073/` (9) |

- `docs/npcs/summary_native/` contains subdirs such as `evidence`, `gm`, `triage`, `cleanup`, `runs`, `draft` and `verify_runs`. Extensions there: 2084 `.md`, 109 `.json`, 4 `.html`, 1 `.py`.
- No `distilled/` subdir under `docs/npcs/`. The path `docs/distill/npcs/` exists separately (232 files; see §6).
- `docs/ensemble/merged_dossiers/` holds 483 files (see §6).
- Full list: `find docs/npcs -type f | sort`
- Direct children only: `find docs/npcs -maxdepth 1 -type f | sort`

### summaries

Published, `docs/summaries/`: 69 files, all `.md`, no subdirs. Names follow `NNN-session-<slug>.md`.
- First: `docs/summaries/002-session-untitled.md`, `003-session-untitled.md`, `004-session-untitled.md`
- Last: `docs/summaries/070-session-untitled.md`, `071-session-untitled.md`, `072-session-the-fixed-point-theory-of-fate.md`
- Full list: `find docs/summaries -type f | sort`

Pipeline output, top-level `summaries/`: 3835 files.
- Chapter dirs: 70, named `YYYY-MM-DD-chapter_NNN[-slug]` (first `2024-11-18-chapter_002`, last `2026-10-19-chapter_73`).
- Other top-level dirs: `old/` (92 files), `recordings/` (53 files), `transcriptions/` (14 files).
- Hidden file: `summaries/.mempalaceignore`
- Extension mix: 1510 `.json`, 1191 `.md`, 327 `.vtt`, 306 `.html`, 207 `.yaml`, 72 `.txt`, 63 `.m4a`, 38 `.log`, 18 `.mp3`.
- Per-chapter contents include `session-summary.md` (70 dirs), `summary.md` (61), `transcript.vtt` (60), `gm-assist.md` (16), plus `staged_review/`, `spell_review/`, `speaker_review/`, `narration/`, `scene_extractions*/`, `logs/` and `.cg/`.
- Full list: `find summaries -type f | sort`
- Per-chapter `session-summary.md` only: `find summaries -name session-summary.md | sort`

### grounding

| Path | State |
|---|---|
| `docs/world_state.md` | present, **symlink** -> `grounding/current/world_state.md` |
| `docs/campaign_state.md` | present, **symlink** -> `grounding/current/campaign_state.md` |
| `docs/party.md` | present, **symlink** -> `grounding/current/party.md` |
| `docs/planning.md` | present, **symlink** -> `grounding/current/planning.md` |
| `docs/canon_events_timeline.md` | present, **symlink** -> `grounding/current/canon_events_timeline.md` |
| `docs/reference` | present, **symlink to a directory** -> `grounding/current/reference` (8 files) |
| `docs/grounding/` | present, 132 files |

- `docs/grounding/current` is a symlink -> `generations/generation-oota-ch072-promote-20261016/live`. Resolved, it holds 13 files: the five `.md` above plus `reference/` (8).
- `docs/grounding/` other entries: `.staging/`, `activations/`, `generations/` (3 generations: `generation-oota-ch071-promote-20261013`, `generation-oota-ch072-promote-20261016`, `legacy-1a91ede33ec8954cb128`; each has `live/`, `published/`, `manifest.json`), `layout.json`, `migrations/`, `operations/`. Extensions: 105 `.md`, 26 `.json`, 1 `.yaml`.
- `docs/grounding_patches.md` (3489 bytes) also exists as a loose file.
- Full list: `find docs/grounding -type f | sort`

### party

| Path | State |
|---|---|
| `docs/party.md` | present (symlink, see above) |
| `docs/party/` | present, 8 files: `Daz-level-08.md`, `Gyrgum-level-08.md`, `Thorin-level-08.md`, `Zalthir-level-08.md`, and `old/level/7/{daz,gyrgum,thorin,zalthir}.md` |
| `docs/party_state.md` | absent |
| `docs/party_extractions/` | present, empty (0 files) |
| `docs/reference/party.md` | present (via the `docs/reference` symlink) |

Per-PC files at `docs/` top level (all regular files):
- `docs/Daz.md` (16875 bytes)
- `docs/Gyrgum.md` (23738)
- `docs/Zalthir.md` (16581)
- `docs/Thorin Giantfriend.md` (14074) — **contains a space**
- `docs/daz_backstory.md` (2592), `docs/gyrgum_backstory.md` (2388), `docs/thorin_backstory.md` (2313), `docs/zalthir_backstory.md` (2875)
- `docs/daz_devir_narrative_arc.md` (12244), `docs/daz_heir.md` (13181)
- `docs/zalthir_power_prompts.md` (3434)

- `voice/` has 15 files: `daz_voice.md`, `gyrgum_voice.md`, `thorin_voice.md`, `zalthir_voice.md`, `vizeran_voice.md`, `_genre.md`, `logs/`, `old_voice/` (5 files).
- `notes/handouts/` includes `20261005-gyrgum-log.md`, `20261012-zalthir-log.md`, `20261019-thorin-log.md` (28 files in the dir).

### prep

`notes/` total: 538 files.

Top-level subdirs of `notes/` and file counts:

| Subdir | Files |
|---|---|
| `canon/` | 1 |
| `chapter_map_review/` | 3 |
| `handouts/` | 28 |
| `imported_underdark/` | 1 |
| `issues/` | 4 |
| `npc_agent/` | 371 |
| `npc_delta/` | 49 |
| `npcs/` | 1 |
| `session_prep/` | 20 |
| `session_reviews/` | 1 |
| `sessions/` | 23 |
| `statblocks/` | 1 |
| `threads/` | 2 |
| `zoom_sync_review/` | 3 |

- `notes/sessions/`: 23 files, all `.md`, no subdirs. Examples: `candlekeep_day_one.md`, `candlekeep_hightower_session_LOCKED.md`, `Kalan to Janussi - Second Petition.md`, `Three Papers - Campaign Placement.md`.
- `notes/session_prep/`: 20 files, `20260615_block2_gyrgumite_disputation.md` through `20261018_gauntlgrym_progress_engine_gm_companion.md`, plus 2 undated names.
- Loose files directly in `notes/` (24 files incl. hidden): `batch_rulings_ch060-070.md`, `bible_divergences.md`, `canon_followups.md`, `chapter_map.json`, `chapter_map.md`, `conspiracy_intersection_summary.md`, `gauntlgrym_faction_summit.md`, `.gitkeep`, `gm_tips.md`, `.mempalaceignore`, `mempalace_pre_cleanup_inventory.md`, `play_boundaries.yaml`, `play_log.md`, `registry_alias_rulings.md`, `renumber_2026-09-26.md`, `renumber_2026-09-27.md`, `.scrub_state.json`, `session_review_template.md`, `session_start_trims.json`, `session_start_trims.md`, `vtt_known_additions.md`, `.vtt_spell_pass_state.json`, `vtt_transcription_corrections.md`, `zoom_media_inventory.md`.
- Full list: `find notes -type f | sort`; `find notes/sessions -type f | sort`

---

## 3. Look-alikes to decide on

Draft, candidate, backup patterns:

| Pattern | Hits under `docs/` + `notes/` |
|---|---|
| `*.old` | `docs/aliases.json.old` |
| `*.bak` | none |
| `*.candidate.*` | none |
| `*_draft*` (file names) | none |
| `draft` directories | `docs/npcs/summary_native/ch002-071/draft/` (179 files), `docs/npcs/summary_native/ch002-073/draft/` (16 files), plus `draft/` dirs under `ch002-072` (35 files) |

Under top-level `summaries/` (outside the §2 scope, listed for completeness): `summaries/old/20260404.old` (dir), `summaries/2026-06-22-chapter_61-the-colloquium-was-well-received/state_draft` (dir), `summaries/2026-10-19-chapter_73/grounding_delta/verify_drafts.py`, and a `*_candidate*` file named `summaries/2026-10-19-chapter_73/grounding_delta/runs/campaign_state.model_candidate.md`.

Staging, extraction, review and similar directories under `docs/` and `notes/` (file counts follow symlinks only where noted):

| Path | Files |
|---|---|
| `docs/authority/` | 6672 |
| `docs/dead/` | 3 |
| `docs/distill/` | 545 |
| `docs/distill/distill_extractions/` | 65 |
| `docs/distill/planning_extractions/` | 118 |
| `docs/distill/campaign_state_extracts/`, `docs/distill/party_extract/` | present as subdirs (counts not taken) |
| `docs/ensemble/` | 3272 |
| `docs/ensemble_summary_prototype/` | 2994 |
| `docs/ensemble_summary_prototype/summary_native/` | 906 |
| `docs/npcs/summary_native/` | 2198 |
| `docs/party/old/` | 4 |
| `docs/party_extractions/` | 0 |
| `docs/planning_extractions/` | 0 |
| `docs/reviews/` | 3046 |
| `docs/state_staging/` | 2 (has `campaign_state/`) |
| `docs/summary_native/` | 6738 |

- No `archive/` dir under `docs/` or `notes/`.
- `docs/summary_native/` holds `TODO.md`, `canon.yaml`, `ch002-070/`, `ch002-071/`, `ch002-072/`.
- `docs/reviews/` holds `campaign.json`, many `npc-review-*` dirs, `promotion-check/`, `promotion-ch071/`.
- `docs/ensemble/` holds `merged.json`, `merged_dossiers/` (483), `per_chapter/`, `per_chapter_rerun/`, `state_dossiers/`, `threads.md`, `thread_proposals.yaml`, `cleanup_worklist.md`, `location_scoped_races.md`.
- Reproduce: `find docs notes -type d \( -name '*_extractions' -o -name state_staging -o -name reviews -o -name summary_native -o -name archive -o -name ensemble -o -name ensemble_summary_prototype -o -name distill -o -name authority -o -name dead -o -name old -o -name draft \)`

---

## 4. Files that would be shared across kinds

Each needs a `mined_as` choice: ______

Precedent (Phandalin): `docs/party.md` was declared in both `party` and `grounding` with `mined_as: true` on grounding. A dir declaration that reaches a file a second time (for example `docs/reference/party.md` via `dirs: [docs/reference]` and a `party` `files:` entry) needs the same choice; `mneme corpus check` reports it if not.

- `docs/party.md` — grounding doc and party data. Symlink to `grounding/current/party.md`. `mined_as` choice: ______
- `docs/reference/party.md` — under the `docs/reference` symlink; reachable from a `docs/reference` declaration and from any `docs/grounding/current/reference` declaration. `mined_as` choice: ______
- `docs/grounding/current/*` — the same five files as `docs/world_state.md` etc., reachable twice (symlink path and real path), and also present under each `docs/grounding/generations/*/live/`. `mined_as` choice: ______
- `docs/npcs/` (all of it) and `docs/npcs/summary_native/` — a `docs/npcs` dir declaration admits `summary_native/` recursively. `mined_as` choice: ______
- `docs/summaries/` and `summaries/` — share chapter content under two roots (published copies and pipeline output). `mined_as` choice: ______
- `docs/Daz.md`, `docs/Gyrgum.md`, `docs/Zalthir.md`, `docs/Thorin Giantfriend.md`, `docs/*_backstory.md` — reachable from a party `files:` list and from any campaign-defined kind that names them. Applies only if both are declared. `mined_as` choice: ______
- `notes/sessions/` and `notes/session_prep/` — both fall under a `notes` dir declaration if `dirs: [notes]` is used. `mined_as` choice: ______

---

## 5. Hazards

### Symlinks (`find docs notes summaries voice -type l`)

Total: 55 (docs 7, notes 0, summaries 48, voice 0).

docs (7):
- `docs/campaign_state.md -> grounding/current/campaign_state.md`
- `docs/canon_events_timeline.md -> grounding/current/canon_events_timeline.md`
- `docs/planning.md -> grounding/current/planning.md`
- `docs/world_state.md -> grounding/current/world_state.md`
- `docs/party.md -> grounding/current/party.md`
- `docs/reference -> grounding/current/reference` (directory)
- `docs/grounding/current -> generations/generation-oota-ch072-promote-20261016/live` (directory)

summaries (48): all `.m4a`, for example `summaries/2025-05-05-chapter_017/GMT20250506-005925_Recording.m4a -> ../recordings/008-20250505/GMT20250506-005925_Recording.m4a`. Full list: `find summaries -type l -printf '%p -> %l\n'`.

Kinds affected: grounding (5 files + `docs/reference`), party (`docs/party.md`, `docs/reference/party.md`), summaries/pipeline (48 `.m4a`).

### Gitignored paths (`find ... -type f | git check-ignore --stdin`)

Totals: docs 3725, notes 6, summaries 126, voice 0.
- `docs/summary_native/` — 3712 of its 6738 files ignored. `.gitignore` rules (lines 60-79) cover `docs/summary_native/ch002-070/state/` and `docs/summary_native/*/state/runs/*/*` (except `record.json`) as runtime state.
- `docs/chapters/.tgrep/` — 6 files ignored (`.gitignore:52: .tgrep/`).
- `notes/.tgrep/` — 6 files (`index.bin`, `files.bin`, `lookup.bin`, `filestamps.json`, `files-extra.bin`, `meta.json`).
- `summaries/**/*.m4a` — rule present; ignored files include per-chapter `logs/` dirs (e.g. `summaries/2026-10-19-chapter_73/logs`, 6 files) and 12+ `summaries/recordings/*` dirs.
- Checked paths with no ignored files: `docs/npcs/`, `docs/summaries/`, `docs/grounding/`, `docs/party/`, `notes/sessions/`.

Kinds affected: none of `npcs`, `summaries` (docs), `grounding`, `party`, `prep` (sessions) paths are ignored. Pipeline `summaries/` and `notes/.tgrep/` are.

Since mneme PR #65 (2026-10-24), gitignored files found under a declared dir are simply not in the corpus; only a gitignored path named in `files:` (or a declared dir itself) is an error. None of the gitignored paths above would be named directly.

Untracked, not ignored (`git ls-files -o --exclude-standard docs notes summaries voice`): 26 files, 1 under `summaries/2026-10-05-chapter_71` and 25 under `summaries/2026-10-19-chapter_73` (e.g. `grounding_delta/legacy_application.lock`).

### Skip-worktree / sparse

`git ls-files -t` from the surveyed directory shows no `S` entries (26457 `H`). Paths outside `out-of-the-abyss/` in the parent repo are `S`.

### Non-text extensions mempalace will not read

- `docs/npcs/`: 109 `.json`, 4 `.html`, 1 `.py`, 4 `.yaml` (in `authored/`); 2180 `.md`.
- `docs/grounding/`: 26 `.json`, 1 `.yaml`; 105 `.md`.
- `docs/summaries/`: none (all `.md`).
- `docs/party/`: none (all `.md`).
- `notes/`: 136 `.json`, 8 `.yaml`, 8 `.html`, 6 `.diff`, 4 `.py`, 4 `.bin` (in `notes/.tgrep/`), 2 `.gitkeep`.
- `notes/sessions/`: none (all `.md`).
- `summaries/`: 63 `.m4a`, 18 `.mp3`, 327 `.vtt`, 306 `.html`, 1510 `.json`, 207 `.yaml`, 72 `.txt`, 38 `.log`.
- `docs/` top level: `aliases.json`, `aliases.json.old`, `connections.json`, `authority.yaml` (1165205 bytes), `corrections.yaml`, `custom_tracking.txt`, `entity_registry.yaml`, `thread_registry.yaml`, `.entity_triage_state.json`, and `docs/TheUnderdark.md` (1080062 bytes, `.md`).

### Filenames containing spaces

Under `docs/` + `notes/` (9, none inside `docs/npcs`, `docs/grounding`, `docs/party` or `docs/summaries`):
- `docs/Thorin Giantfriend.md` — party
- `docs/background/Ilvara reflecting on the Ember Vanguard.md` — background
- `docs/background/Out of the Abyss.md` — background
- `docs/dead/Deals deep dive.md`, `docs/dead/Deals made in Gracklstugh.md`, `docs/dead/Escape from the Neverlight Grove.md` — dead
- `notes/sessions/Bookwyrm to Janussi - Regarding the Gatewarden's Second Petition.md` — prep (also contains an apostrophe)
- `notes/sessions/Kalan to Janussi - Second Petition.md` — prep
- `notes/sessions/Three Papers - Campaign Placement.md` — prep

Under `summaries/`: 25 files with spaces, e.g. `summaries/2024-12-09-chapter_005/2024-12-09 DND Underdark EP 5.md`, `summaries/2026-10-05-chapter_71/GMT20261006-005839_Recording.transcript (1).vtt` (also has parentheses). Reproduce: `find summaries -name '* *'`.

Kinds affected: party (1), prep (3), summaries/pipeline (25), plus the candidate kinds in §6 (`docs/background/`, `docs/dead/`).

---

## 6. Candidate campaign kinds

Loose `docs/*.md`: 29 files. Other loose files in `docs/` are listed below.

Directories under `docs/` outside the five standard kinds (file counts):

| Path | Files | Notes |
|---|---|---|
| `docs/chapters/` | 68 | `chapter_NN_<slug>.md`; `.tgrep/` ignored |
| `docs/gauntlgrym/` | 7 | `README.md`, `gauntlgrym_asset_table.md`, `faction_asset_network.md`, `dm_guide_faction_assets.md`, `gauntlgrym_bruenor_scene_script.md`, `gauntlgrym_faction_pitches.md`, `gyrgum_stroud_echo_scene_packet.md` |
| `docs/reference/` | 8 | symlink dir: `npcs.md`, `factions.md`, `locations.md`, `party.md`, `items.md`, `threads.md`, `threads_unratified.md`, `threats.md` |
| `docs/tracking/` | 3 | `tracking.txt`, `tracking_blingdenstone_travelogue.txt`, `tracking_candlekeep_murders.txt` |
| `docs/inventory/` | 2 | `out-of-the-abyss-inventory.md`, `candlekeep_murders_module_inventory.md` |
| `docs/background/` | 9 | includes `Out of the Abyss.md`, two `.json` module files, `gracklstugh-revised-inventory.{md,txt}`, `post_oota_vhaerun_arc.md` |
| `docs/dead/` | 3 | |
| `docs/distill/npcs/` | 232 | |
| `docs/ensemble/merged_dossiers/` | 483 | |

Loose files in `docs/` (top level):
- Design and canon: `campaign_design_frame.md`, `campaign_master_plan.md`, `canon_guardrails.md`, `canon_events_timeline.md` (symlink), `decision_ladders.md`, `risk_levers.md`, `heat.md` (380 bytes), `mechanics.md` (98 bytes), `endgame_design_process.md`, `endgame_extension_rationale.md`, `coalition_assets_underdark.md`
- Registry and data: `thread_registry.yaml` (23 bytes), `entity_registry.yaml`, `entity_inventory.md`, `aliases.json`, `connections.json`, `corrections.yaml`, `authority.yaml`, `custom_tracking.txt`, `grounding_patches.md`, `TheUnderdark.md`
- State: `.entity_triage_state.json`

Outside `docs/`:
- `voice/` — 15 files
- `notes/handouts/` — 28; `notes/npc_agent/` — 371; `notes/npc_delta/` — 49; `notes/session_prep/` — 20; `notes/threads/` — 2; `notes/statblocks/` — 1; `notes/issues/` — 4
- Other top-level directories in the checkout: `config/`, `examples/`, `lib/`, `logs/`, `tools/`

Reproduce: `find docs -mindepth 1 -maxdepth 1 | sort`; `find docs -maxdepth 1 -type f | sort`

---

## 7. GM decisions (2026-10-25)

Every choice below is an explicit GM answer, given in three question rounds on 2026-10-25. The resulting `.mneme/corpus.yaml` dry-resolved to **292 distinct files with 0 findings**, and `mneme corpus check` reports it valid.

| Kind | Trust | Files | Decision |
|---|---|---|---|
| `npcs` | authoritative | 96 | Only the top-level `docs/npcs/*.md`, listed under `files:`. Out: `authored/` (4 yaml overrides) and `summary_native/`. |
| `summaries` | authoritative | 69 | `dirs: [docs/summaries]` only. Out: the pipeline `summaries/*/session-summary.md`. |
| `party` | authoritative | 8 (+`docs/party.md`) | The current level-9 sheets `docs/{Daz,Gyrgum,Zalthir,Thorin Giantfriend}.md` and the 4 `docs/*_backstory.md`. `docs/party.md` is declared here too, but mined as grounding. Out: the level-8 sheets in `docs/party/`. |
| `grounding` | authoritative | 15 | The 5 grounding symlinks, `dirs: [docs/reference]`, `docs/grounding_patches.md` and `docs/mechanics.md`; `mined_as: true`. |
| `prep` | reference | 88 | `notes/{session_prep,sessions,handouts,threads,statblocks,npcs,imported_underdark}` and `docs/gauntlgrym`, plus `notes/{gauntlgrym_faction_summit,conspiracy_intersection_summary,gm_tips,play_log}.md` and `docs/zalthir_power_prompts.md`. |
| `lore` (campaign kind) | authoritative | 10 | `docs/{campaign_master_plan,campaign_design_frame,canon_guardrails,decision_ladders,risk_levers,heat,coalition_assets_underdark,endgame_extension_rationale,daz_heir,daz_devir_narrative_arc}.md`. |
| `module` (campaign kind) | reference | 6 | `dirs: [docs/inventory]` and `docs/background/{Out of the Abyss, gracklstugh-revised-inventory, Ilvara reflecting on the Ember Vanguard, post_oota_vhaerun_arc}.md`. Out: the byte-identical inventory copies in `docs/background`, the `.txt` name list, and the 2 Candlekeep JSON files. |

Also decided:
- **Narrative:** `docs/chapters/` and the bible `docs/TheUnderdark.md` are both left out, as in Phandalin. CampaignGenerator's old `narrative` canon wing goes away.
- **Left out:** `docs/dead/`, `docs/endgame_design_process.md`, `notes/canon_followups.md`, `notes/bible_divergences.md`, `notes/issues/`, `notes/session_reviews/`, and every pipeline dir (`notes/npc_agent`, `notes/npc_delta`, `docs/summary_native`, `docs/ensemble*`, `docs/distill`, `docs/reviews`, `docs/authority`, `docs/grounding/generations`).
- **Root `mempalace.yaml`:** untracked (`git rm --cached`) and left to the bare ignore rule, like Phandalin's generated file. The legacy `palace: abyss` content stays in git history.
- **Palace name:** `out-of-the-abyss`.
- Canon wings: `npcs`, `summaries`, `party`, `grounding`, `lore`. Index wings: `prep`, `module`.

The `corpus.yaml` as written to `out-of-the-abyss/.mneme/corpus.yaml`:

```yaml
campaign: out-of-the-abyss
kinds:
  npcs:
    files:
    - docs/npcs/a-lai-aivenmore.md
    - docs/npcs/alaundo-the-seer.md
    - docs/npcs/alkrist.md
    - docs/npcs/araumycos.md
    - docs/npcs/asha-vandree.md
    - docs/npcs/batman.md
    - docs/npcs/bookwyrm-first-reader.md
    - docs/npcs/brannum-redmarch.md
    - docs/npcs/brother-hilmin-thaer.md
    - docs/npcs/bruenor-battlehammer.md
    - docs/npcs/brysis-of-khaem.md
    - docs/npcs/buppido.md
    - docs/npcs/chef-goromach.md
    - docs/npcs/chipgrin-goldwhisker.md
    - docs/npcs/daral-yashenti.md
    - docs/npcs/dasco-pickshine.md
    - docs/npcs/dawnbringer.md
    - docs/npcs/demogorgon.md
    - docs/npcs/dorbo-diggermattock.md
    - docs/npcs/droki.md
    - docs/npcs/dynaphyse.md
    - docs/npcs/edvaldo-sedanur.md
    - docs/npcs/eldeth-feldrun.md
    - docs/npcs/errde-blackskull.md
    - docs/npcs/fargas-rumblefoot.md
    - docs/npcs/fembris-lancer.md
    - docs/npcs/fheminor-scrivenbark.md
    - docs/npcs/flumph.md
    - docs/npcs/gartokkar-xundorn.md
    - docs/npcs/glabbagool.md
    - docs/npcs/gorglak.md
    - docs/npcs/grula-munga.md
    - docs/npcs/gurnik-tapfinger.md
    - docs/npcs/hemeth.md
    - docs/npcs/horgar-steelshadow-v.md
    - docs/npcs/house-t-sarran-spy.md
    - docs/npcs/ilvara-mizzrym.md
    - docs/npcs/imbros.md
    - docs/npcs/inda.md
    - docs/npcs/irony.md
    - docs/npcs/jadger.md
    - docs/npcs/janussi.md
    - docs/npcs/jimjar.md
    - docs/npcs/jorlan-duskryn.md
    - docs/npcs/kaelira-duskryn.md
    - docs/npcs/kalan-strongbranch.md
    - docs/npcs/kazook-pickshine.md
    - docs/npcs/kazryn-nyantani.md
    - docs/npcs/khell-vire.md
    - docs/npcs/leuwin.md
    - docs/npcs/manshoon-simulacrum.md
    - docs/npcs/manshoon.md
    - docs/npcs/miirym-the-sentinel-wyrm.md
    - docs/npcs/miss-hollypocket.md
    - docs/npcs/moziqodo.md
    - docs/npcs/narrak.md
    - docs/npcs/neheedra-duskryn.md
    - docs/npcs/nibbles.md
    - docs/npcs/nomi-pathshutter.md
    - docs/npcs/nym-duskryn.md
    - docs/npcs/pelek.md
    - docs/npcs/philemon-master-archivist.md
    - docs/npcs/pizwog.md
    - docs/npcs/plinki.md
    - docs/npcs/prince-derendil.md
    - docs/npcs/prince-livid.md
    - docs/npcs/princess-ebonmire.md
    - docs/npcs/protanther.md
    - docs/npcs/ront.md
    - docs/npcs/rumpadump.md
    - docs/npcs/sarith-kzekarit.md
    - docs/npcs/senni-diggermattock.md
    - docs/npcs/shuushar-the-awakened.md
    - docs/npcs/sister-yvenne.md
    - docs/npcs/sovereign-basidia.md
    - docs/npcs/sovereign-phylo.md
    - docs/npcs/spanner.md
    - docs/npcs/spiderbait.md
    - docs/npcs/stonespeaker-hgraam.md
    - docs/npcs/stool.md
    - docs/npcs/stroud.md
    - docs/npcs/sylvira-savikas.md
    - docs/npcs/tadric.md
    - docs/npcs/teles-ahvoste.md
    - docs/npcs/the-flying-iron-owlbear.md
    - docs/npcs/the-pudding-king.md
    - docs/npcs/themberchaud.md
    - docs/npcs/topsy-and-turvy.md
    - docs/npcs/topsy.md
    - docs/npcs/turvy.md
    - docs/npcs/vareth.md
    - docs/npcs/werz-saltbaron.md
    - docs/npcs/whistler.md
    - docs/npcs/yestabrod.md
    - docs/npcs/yuk-yuk.md
    - docs/npcs/zuggtmoy.md
  summaries:
    dirs:
    - docs/summaries
  party:
    files:
    - docs/Daz.md
    - docs/Gyrgum.md
    - docs/Zalthir.md
    - docs/Thorin Giantfriend.md
    - docs/daz_backstory.md
    - docs/gyrgum_backstory.md
    - docs/thorin_backstory.md
    - docs/zalthir_backstory.md
    - docs/party.md
  grounding:
    dirs:
    - docs/reference
    files:
    - docs/world_state.md
    - docs/campaign_state.md
    - docs/party.md
    - docs/planning.md
    - docs/canon_events_timeline.md
    - docs/grounding_patches.md
    - docs/mechanics.md
    mined_as: true
  prep:
    dirs:
    - notes/session_prep
    - notes/sessions
    - notes/handouts
    - docs/gauntlgrym
    - notes/threads
    - notes/statblocks
    - notes/npcs
    - notes/imported_underdark
    files:
    - notes/gauntlgrym_faction_summit.md
    - notes/conspiracy_intersection_summary.md
    - notes/gm_tips.md
    - notes/play_log.md
    - docs/zalthir_power_prompts.md
campaign_kinds:
  lore:
    files:
    - docs/campaign_master_plan.md
    - docs/campaign_design_frame.md
    - docs/canon_guardrails.md
    - docs/decision_ladders.md
    - docs/risk_levers.md
    - docs/heat.md
    - docs/coalition_assets_underdark.md
    - docs/endgame_extension_rationale.md
    - docs/daz_heir.md
    - docs/daz_devir_narrative_arc.md
    trust: authoritative
  module:
    dirs:
    - docs/inventory
    files:
    - docs/background/Out of the Abyss.md
    - docs/background/gracklstugh-revised-inventory.md
    - docs/background/Ilvara reflecting on the Ember Vanguard.md
    - docs/background/post_oota_vhaerun_arc.md
    trust: reference
```

## 8. Blank decision checklist (survey-time, superseded by section 7)


| Kind | dirs / files | trust override | `mined_as` |
|---|---|---|---|
| `npcs` | ______ | ______ | ______ |
| `summaries` | ______ | ______ | ______ |
| `party` | ______ | ______ | ______ |
| `grounding` | ______ | ______ | ______ |
| `prep` | ______ | ______ | ______ |

Campaign kinds (name, dirs/files, trust — required): ______

Also decide (section 0): `docs/chapters` in or out ______; `docs/npcs/authored/` ______; root `mempalace.yaml` commit or untrack ______; palace name `out-of-the-abyss` ______.

Blank skeleton:

```yaml
campaign: out-of-the-abyss

kinds:
  npcs:
    # dirs: []
    # files: []
  summaries:
    # dirs: []
    # files: []
  party:
    # dirs: []
    # files: []
  grounding:
    # dirs: []
    # files: []
  prep:
    # dirs: []
    # files: []

campaign_kinds:
```
