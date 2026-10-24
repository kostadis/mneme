# Corpus worksheet — phandalin

- Surveyed path: `/home/kostadis/phandalin/Phandalin` (git root is the parent, `/home/kostadis/phandalin`; `core.sparseCheckout` is true there)
- HEAD: `520afd44` (`git -C /home/kostadis/phandalin rev-parse HEAD` = `520afd441df1cc5a0a3c5eb5ea22e22a36aab99c`, committed 2026-10-22)
- Date: 2026-10-24
- There is **no** `.mneme/` directory (no mneme authority). `config/config.yaml` has no `mempalace:` section; CampaignGenerator falls back to defaults (canon wing `narrative`, index wings `chronicle` and the campaign name).

Observations only. Nothing here is a decision; the GM writes `.mneme/corpus.yaml`.

Sparse-checkout state: `git ls-files -t` across the whole parent repo shows 15172 `H` and 40330 `S`. Restricted to `Phandalin/` it shows 15097 `H` and no `S`. Under `docs notes summaries characters voice wiki` there are 0 `S` entries.

Counting convention: counts are files (`find <path> -type f`) unless stated. Counts that include tool-state dirs (`.zvec-grep/`, `.tgrep/`) are noted. Symlinked directories are not followed.

---

## 1. What the palace mines today

State: **no mneme authority**. There is no `.mneme/mempalace.yaml`, so there are no mneme-declared wings, sources, trust values or `extra_exclusions`.

`mempalace.yaml` files anywhere under the campaign:
- Under the surveyed directory `/home/kostadis/phandalin/Phandalin`: **none found** (`find Phandalin -name 'mempalace.yaml*'` returns nothing). `docs/chapters/mempalace.yaml`, `notes/mempalace.yaml` and `summaries/mempalace.yaml` do not exist here. (`notes/.mempalaceignore` mentions `mempalace.yaml` in its "self-referential" lines.)
- One in the git root, outside the surveyed directory: `/home/kostadis/phandalin/mempalace.yaml`. It is tracked, carries the header `# mneme-rendered; source-sha256: 2fe24e74...; do-not-edit`, and reads `palace: hillsfar`, `wing: hillsfar`, rooms `npcs party world arcs general`. It names no source path and no trust.

So the wings that "mine today" cannot be read from any `mempalace.yaml` in the surveyed directory. The only mining-related files in it are:

`Phandalin/.mempalaceignore` (tracked, hand-written, verbatim entries):
```
docs/chapters/
docs/distill_extractions/
docs/state_extractions/
docs/party_extractions/
docs/synthesize_npc/
docs/planning_extractions/
docs/chapter_extracts/
docs/level/
docs/adventures/
docs/background/
docs/NeverwinterExpansionismandtheNorth.md
notes/
brewbarry.md
vukradin.md
vukradin-6.pdf
characters/
docs/party/
docs/npcs/brewbarry.md
docs/npcs/soma.md
docs/npcs/valphine.md
docs/npcs/valphine_sortorra.md
docs/npcs/vukradin.md
docs/Backstory - Brewbarry.md
docs/Backstory - Valphine Sotorra.md
docs/Soma - Backstory.md
voice/
examples/
summaries/
config.yaml
config/
ui_config.yaml
*.sh
lib/
entities.json
mempalace.yaml
connections.json
logs/
.claude/
MEMPALACE.md
docs/world_state_draft.md
docs/tracking.txt
docs/tracking-*.txt
docs/npcs.backup-*.tar.gz
docs/gdriveMD
desktop.ini
*.Zone.Identifier
```
(Comment lines omitted. Its comments say `docs/chapters/` and `docs/distill_extractions/` are "separate wings (mined independently)", and `notes/` is "working/staging area (not canon yet)", `summaries/` is "raw session data".)

Other `.mempalaceignore` files: `docs/chapters/.mempalaceignore` (`.claude/`), `notes/.mempalaceignore` (`*.py *.json *.db *.txt .gitkeep`, three VTT metadata files, three meta docs, `mempalace.yaml`, `.mempalaceignore`), `summaries/.mempalaceignore` (`*.vtt vtt.cleaned.md vtt.md logs/ .cg/ *.knobs.json *.db *.scaffold.md* *.prev *.log *.txt *.doc` and several narration/consistency report names). The git-root `/home/kostadis/phandalin/.mempalaceignore` is mneme-rendered (`logs/ voice/ examples/ .claude/ .mneme/ .mcp.json MEMPALACE.md *.sh config.yaml ui_config.yaml ui_state.yaml entities.json refs.yaml refs.local.yaml .dedup_state.json`).

`Phandalin/MEMPALACE_HORIZON.md` (verbatim facts): last campaign chapter played "A Storm of Bolts and Orcs" (session-summary "Chapter 42"); last bible chapter file `docs/chapters/chapter_42_a_storm_is_coming.md`; last session date 2026-05-19; palace last (re)mined 2026-05-22 (incremental; +33 `extract_043`, +49 chapter file, +571 drawers across 32 "phandalin-wing" files); embedding device CPU (onnxruntime). The horizon predates the current content: `summaries/` now runs through chapter 59 (2026-10-20) and `docs/chapters/` holds 51 chapter files.

Wings named by the horizon file and the ignore comments: a `narrative` wing from `docs/chapters/` (flagged: it drops out of the palace unless declared), a `phandalin` wing, and a `distill_extractions` wing; `docs/chapters/` and `docs/distill_extractions/` are in `.mempalaceignore` because they were mined as separate wings. No `mempalace.yaml` here confirms their trust values.

Palace contents: `~/.mempalace/palaces/` holds only `chat`, `hallways.json`. `~/.mempalace/config.json` registers only the `chat` palace. No Phandalin palace exists under `~/.mempalace/`, and no palace path is named by any `mempalace.yaml` in the campaign (the git-root one names palace `hillsfar`, which is not present under `~/.mempalace/palaces/`). Per-wing counts: not readable. No status command was run; nothing under `~/.mempalace` was queried.

Palace contents not surveyed: no read-only source listing exists until T005.

## 2. Files at each standard kind's usual locations

### npcs
- `docs/npcs/` total: 991 files
  - top level: 100 files (all `.md`)
  - `docs/npcs/summary_native/`: 891 files
    - `ch002-057/`: 805 (`evidence` 173, `gm` 95, `verification_review` 3, `runs` 318, `draft` 191, `verify_runs` 21)
    - `ch002-059/`: 60 (`evidence` 15, `gm` 15, `draft` 30)
    - `ch058-059/`: 25 (`evidence` 22)
    - `publish_log.json`: 1
  - `docs/npcs/distilled/`: absent
  - `docs/npcs/authored/`: absent
- No `.dedup_state.json` or draft/backup-named files at the top level of `docs/npcs/`.
- No file named for the four PCs at the top level of `docs/npcs/` (no `brewbarry`, `vukradin`, `soma`, `valphine`), although `.mempalaceignore` lists five such paths.
- Related, outside `docs/npcs/`: `docs/distill/npcs/` (492 files), `docs/synthesize_npc/` (9), `notes/npcs/` (11), `notes/npc_agent/` (99), `notes/npc_delta/` (41).
- Reproduce: `find docs/npcs -type f | wc -l`

### summaries
- `docs/summaries/` (published): 58 `.md` files, `002-session-untitled.md` ... `059-session-untitled.md`, plus a tool-state dir `docs/summaries/.zvec-grep/` (92 files; 150 total).
- `summaries/` (pipeline output): 3132 files, no tool-state dirs inside it.
  - Top-level entries (61): 58 session dirs `2025-05-14-chapter_02` ... `2026-10-20-chapter_59` (from 1 file for `2025-07-15-chapter_09-...` up to 150 for `2026-09-02-chapter_54-...`), `attempts/` (103), `vtt_spell_pass_20251112_20260318/` (236), `vtt_spell_pass_20260318_20260818/` (134), and `.mempalaceignore`.
  - `session-summary.md` files: 147. `.md` files total: 1278.
  - Other extensions: json 851, vtt 467, html 150, yaml 147, txt 63, reviewed 56, py 32, prev 23, jsonl 14, diff 11, m4a 5, log 5, db 5, patch 3, plus smaller counts.
  - Subdir names seen inside session dirs (count of dirs): `narration` 17, `.cg` 14, `staged_review` 13, `scene_extractions` 13, `scene_extractions_smoothed` 9, `scene_extractions_new` 9, `vtt_roleplay_extractions` 5, `vtt_extractions` 5, `spell_review` 3, `speaker_attribution` 3, `narration_wiki` 2, `logs` 2, and one each of `zoom_source`, `voice_critic`, `scene_extractions_rebuilt`, `narration_prompt_test`, `narration_dgx`, `narration3`, `narration2`, `hand-edited`, `haiku`, `dialogue_edit`, `followup1..7_*_scripts`.
- Related: `docs/summary_native/` (710: `ch002-057` 636, `ch058-059` 73, `canon.yaml` 1), which sits beside `docs/summaries/` and is a pipeline dir.
- Reproduce: `find summaries -type f | wc -l`; `ls summaries`

### grounding
- `docs/world_state.md`: present (31779 bytes)
- `docs/campaign_state.md`: present (94096 bytes)
- `docs/party.md`: present (11287 bytes)
- `docs/planning.md`: present (31272 bytes)
- Also present at `docs/`: `world_state_synth.md` (279 lines), `docs/mechanics.md` (3 lines, listed in `config/config.yaml` as a document next to the four), `docs/grounding_sections/` (10 files: `campaign_state/` 3, `planning/` 3, `world_state/` 4), `docs/projections/` (3 `*_draft.md`, see section 3).

### party
- `docs/party.md`: present (also a grounding doc, see section 4)
- `docs/party/`: present, 8 files: `Soma.md`, `Vukradin.md`, `Valphine Sotorra.md`, `Brewbarry.md`, and `old/level/5/` with `Soma.md`, `Valphine.md`, `Vukradin.md`, `Brewbarry.md`
- `docs/party_state.md`: absent
- `characters/`: 8 files: `brewbarry.md`, `vukradin.md`, `soma.md`, `valphine.md`, and `old/` with `brewbarry.md`, `vukradin.md`, `valphine.md`, `soma5.md`
- `docs/Backstory - Brewbarry.md`, `docs/Backstory - Valphine Sotorra.md`, `docs/Soma - Backstory.md` (no Vukradin backstory found at `docs/`)
- `examples/`: 4 files (`brewbarry.md`, `soma.md`, `valphine.md`, `vukradin.md`)
- `voice/`: 20 files (`_genre.md`, 4 `*_new_pipeline.md`, `v1/` with per-PC voice files and subdirs `vukradin/`, `valphine/`, `soma/`)
- `config/party.yaml`, `config/players.yaml`
- `docs/party_extractions/`: 44 files (`extract_001.md` ...)
- Per-PC tracking: `docs/tracking/` has `brewbarry-score.md`, `soma-score.md`, `valphine-score.md`, `echoes-score.md`, `grundar_score.md`, `aletra-sortorra-arc.md`, `Adabra quest line.md`, `splinter-colony.md` (8 files)
- `*_backstory*` files: none found by that lowercase pattern

### prep
- `notes/sessions/`: absent
- `notes/` total: 432 files. Top-level dirs and file counts: `arc_cleanup` 17, `art` 3, `chapter_map_review` 1, `claudien` 2, `corrections` 4, `grounding_delta` 135, `handouts` 14, `KP` 5, `neverwinter` 12, `npc_agent` 99, `npc_delta` 41, `npcs` 11, `recording_gap_batch` 8, `session_prep` 30, `spell_pass_batch` 24.
- `notes/session_prep/` (30 files, all direct): 21 dated from `20260531_rimardo_corrin_at_the_lodge.md` to `20261021_machine_room_under_control.md`, plus `circle_of_thunder.md`, `counterattack_lodge.md`, `manse_arrival.md`.
- `notes/handouts/` (14): includes `01_aldus_mayoral_appointment.md`, `02_phandalin_welcome_and_confirmation.md`, `player_quest_log.md` and per-PC logs such as `20261020-vukradin-log.md`, `20261027-soma-log.md`.
- Loose files directly in `notes/` (examples): `chapter_map.md`, `chapter_map.json`, `halia_thornton_strategy.md`, `party_arc_tracks_addendum.md`, `recording_reconciliation_2026-10-07.md`, `renumber_2026-10-07.md`, `scrub_register_policy.md`, `vtt_known_additions.md`, `vtt_transcription_corrections.md`, `mempalace_usage_guide.md`, `VERIFICATION.md`.
- Reproduce: `find notes -maxdepth 1 -mindepth 1`; `find notes/<dir> -type f | wc -l`

## 3. Look-alikes to decide on

Drafts / candidates / backups:
- `docs/party.candidate.md` (220 lines)
- `docs/projections/campaign_state_draft.md`
- `docs/projections/planning_draft.md`
- `docs/projections/world_state_draft.md`
- `docs/world_state_synth.md` (matches neither pattern; listed by name)
- `summaries/2026-06-09-chapter_48-victory-lap/session-summary.md.old`
- `summaries/2026-05-12-chapter_44-unraveling-the-storm-gods-secrets/narration/consistency_report.md.old`
- `docs/world_state_draft.md` is named in `.mempalaceignore` but does not exist on disk.
- No `*.bak` found under `docs notes characters voice wiki summaries`. `summaries/` also holds 56 `.reviewed`, 23 `.prev` and 4 `.unused-no-speakers` files.

Staging / extraction / review dirs:
- `docs/archive/` (12 files: `{campaign_state,world_state,planning,party}_ch0{2,3,4}.md`)
- `docs/reviews/` (2751 files; 5 `npc-review-*` dirs: 10, 870, 869, 131, 870)
- `docs/summary_native/` (710) and `docs/npcs/summary_native/` (891)
- `docs/ensemble/` (254: `per_chapter` 159, `state_dossiers` 90, plus `aliases.json`, `events.jsonl`, `merged.json`, `thread_proposals.yaml`, `threads.md`)
- `docs/distill/` (666: `npcs` 492, `planning_extractions` 87, `distill_extractions` 44, `state_extractions` 43)
- `docs/party_extractions/` (44), `docs/chapter_extracts/` (36), `docs/synthesize_npc/` (9), `docs/grounding_sections/` (10), `docs/projections/` (3)
- `docs/authority/` (5966: `snapshots` 5844, `events` 58, `transactions` 63, plus `.lock`)
- `docs/dead/` (5), `docs/party/old/` (4), `characters/old/` (4)
- `notes/grounding_delta/` (135), `notes/npc_delta/` (41), `notes/npc_agent/` (99), `notes/arc_cleanup/` (17), `notes/recording_gap_batch/` (8), `notes/spell_pass_batch/` (24)
- `summaries/attempts/` (103), `summaries/vtt_spell_pass_*/` (236 and 134); per-session `scene_extractions*`, `vtt_extractions`, `staged_review`, `narration*` dirs (section 2)
- `state_staging/`: not found.

Reproduce: `find docs notes characters summaries \( -iname '*_draft*' -o -iname '*.candidate.*' -o -name '*.bak' -o -name '*.old' -o -name '*_extractions' -o -name state_staging -o -name reviews -o -name summary_native -o -name archive -o -name ensemble \)`

## 4. Files that would be shared across kinds

- `docs/party.md`: grounding doc and party data; needs a `mined_as` choice: ______
- `docs/campaign_state.md`, `docs/world_state.md`, `docs/planning.md`: no second kind observed at the usual locations; GM to confirm. (`config/config.yaml` also lists `docs/mechanics.md` as a document beside the four.)
- `docs/summaries/` vs `summaries/`: different directories with different content; no shared files observed.
- `docs/party/` and `characters/` hold same-named PC files (`brewbarry.md`, `vukradin.md`, `soma.md`, `valphine.md`) in different dirs, plus `docs/party/old/level/5/` and `characters/old/` copies; observation only.
- `docs/npcs/summary_native/` sits under a standard-kind dir and shares the name of `docs/summary_native/`; observation only.
- `notes/handouts/` per-PC logs and `player_quest_log*.md` name the PCs; they sit under `notes/`; observation only.

## 5. Hazards

- Symlinks (`find . -type l` excluding `.git`; and `find docs notes summaries characters voice wiki -type l`): none found. `docs/gdriveMD` ("Symlinks to external sources" per `.mempalaceignore`) does not exist.
- Gitignored paths (`git check-ignore`): 262 files under `docs notes summaries characters voice wiki` are ignored (`docs` 253, `notes` 1, `summaries` 8, others 0).
  - `docs/ensemble/per_chapter/` (159; `.gitignore` line 18), plus `docs/ensemble/merged.json`
  - `docs/summaries/.zvec-grep/` (92)
  - `docs/authority/.lock`
  - `notes/npc_delta/ch058-059/__pycache__/changes.cpython-314.pyc`
  - `summaries/`: 5 `.m4a` (`*.m4a` ignored) and 3 files in `logs/` of chapters 58 and 59
  - Reproduce: `find docs notes summaries characters voice wiki -type f | git check-ignore --stdin`
- Skip-worktree / sparse (`git ls-files -t`): 0 `S` entries under the surveyed directory or under any of the dirs above.
- Nested git: `Phandalin/.git` exists as an **empty directory** (not a repo). `summaries/` session dirs hold `.cg/` dirs (14).
- Non-text extensions under `docs notes summaries characters voice wiki`: `docs/background/3627966-Factions_of_Phandalin_4.5.1.pdf`; `summaries/2026-09-15-chapter_56-the-fall-of-the-rift-weaver-prime/session_2026_09_15_chapter_53_the_fall_of_the_rift_weaver_prime_transcript.docx`; 5 `.m4a` under `summaries/` (gitignored): chapters 54, 55, 57, 58, 59. `.mempalaceignore` also names `vukradin-6.pdf` and `docs/npcs.backup-*.tar.gz` (neither found). Binary store files (`.sst`, rocksdb, `.zvec`) sit inside `.zvec-grep/` and `.tgrep/` dirs.
- Tool-state dirs: `Phandalin/.zvec-grep/` (101 files), `Phandalin/.tgrep/` (6), `docs/summaries/.zvec-grep/` (92).
- `docs/npcs/` counts, `docs/summaries/` (150 total) and `docs/` (11761 total) include or exclude tool-state files as stated in section 2.

## 6. Candidate campaign kinds

Directories holding material outside the five standard kinds (path and count only):
- `docs/chapters/`: 52 files (51 `chapter_NN_*.md`, `chapter_01_neverwinter_expansionism_...` ... `chapter_51_we_re_famous_why_are_we_famous.md`, plus `.mempalaceignore`); the `narrative` wing source under CampaignGenerator defaults
- `characters/`: 8 files (+4 in `old/`)
- `voice/`: 20 files
- `wiki/`: 4 files (`index.md`, `logs.md`, `patterns/` with 2)
- `examples/`: 4 files
- `docs/background/`: 31 files (module text, scans, inventories, monster reference, one PDF)
- `docs/adventures/`: 6 files
- `docs/reference/`: 6 (`factions.md`, `items.md`, `locations.md`, `npcs.md`, `threads.md`, `threats.md`)
- `docs/tracking/`: 8 files; plus `docs/tracking.txt`, `docs/tracking-*.txt` (3)
- `docs/dead/`: 5
- `docs/authority/`: 5966; `docs/reviews/`: 2751
- `notes/KP/`: 5; `notes/neverwinter/`: 12; `notes/claudien/`: 2
- Tracking / reference files directly under `docs/` (43 files in total at that level): `aliases.json`, `authority.yaml`, `canon_events_timeline.md`, `chapter_provenance.md`, `connections.json`, `corrections.yaml`, `document_hierarchy.md`, `entity_inventory.md`, `entity_registry.yaml`, `glossary.md`, `gm_doctrine.md`, `thread_registry.yaml`, `campaign arc.md`, `KP.md`, `Kraken society.md`, `CounterForce.md`, `Fame.md`, and named NPC/org files (`Adabra — The Fanatical Naturalist.md`, `Aletra.md`, `Brundar.md`, `Corbin.md`, `Margaster.md`), `NeverwinterExpansionismandtheNorth.md`
- Other root entries: `config/` (11 entries, incl. `agents/`), `lib/` (3 dirs), `output/` (`pdf/`), `entities.json`, `*.sh` (3), `CLAUDE.md`, `MEMPALACE_HORIZON.md`

## 7. Decision checklist

Leave blank; GM fills in.

- [ ] `npcs`: dirs ______ files ______ trust override ______ mined_as ______
- [ ] `summaries`: dirs ______ files ______ trust override ______ mined_as ______
- [ ] `party`: dirs ______ files ______ trust override ______ mined_as ______
- [ ] `grounding`: dirs ______ files ______ trust override ______ mined_as ______
- [ ] `prep`: dirs ______ files ______ trust override ______ mined_as ______
- [ ] campaign kinds (name / dirs / files / trust): ______

Blank skeleton:

```yaml
campaign: phandalin

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
