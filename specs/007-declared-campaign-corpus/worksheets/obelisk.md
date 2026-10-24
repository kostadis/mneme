# Corpus worksheet — obelisk

- Surveyed path: `/home/kostadis/obelisk/obelisk` (git root is the parent, `/home/kostadis/obelisk`)
- HEAD: `f80a2be1` (committed 2026-10-19)
- Date: 2026-10-23

Observations only. Nothing here is a decision; the GM writes `.mneme/corpus.yaml`.

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

## 7. Decision checklist

| kind | dirs / files | trust override | mined_as |
|---|---|---|---|
| npcs | ______ | ______ | ______ |
| summaries | ______ | ______ | ______ |
| party | ______ | ______ | ______ |
| grounding | ______ | ______ | ______ |
| prep | ______ | ______ | ______ |
| campaign kinds (name, paths, trust) | ______ | ______ | n/a |

Blank skeleton:

```yaml
campaign: obelisk

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
