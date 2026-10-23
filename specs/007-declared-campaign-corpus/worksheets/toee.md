# Corpus worksheet — toee

- Surveyed path: `/home/kostadis/toee/toee` (sparse git checkout; repo root `/home/kostadis/toee`)
- HEAD: `5961792f` (`git -C /home/kostadis/toee rev-parse --short HEAD`)
- Date: 2026-10-23
- A second, older copy exists at `/home/kostadis/src/campaigns/toee`. It was not surveyed.

Observations only. Nothing here is a decision; the GM writes `.mneme/corpus.yaml`.

---

## 1. What the palace mines today

Source: `.mneme/mempalace.yaml` (campaign `toee`, recipe_version `2.0.0`, store alias `toee`).

| Wing | source | trust | Flag |
|---|---|---|---|
| `chronicle` | `docs/distill_extractions` | accelerator | |
| `prep` | `notes/sessions` | reference | |
| `notes` | `notes` | reference | |
| `summaries` | `summaries` | reference | |
| `toee` | `.` | **authoritative** | drops out of the palace unless declared |

- The `toee` wing is the root wing (`source: .`) and is the only `trust: authoritative` wing. It drops out of the palace unless declared.
- The root wing's source is the whole checkout. Within `docs/`, `config/`, `MEMPALACE.md`, `ui_state.yaml` etc., what remains after `extra_exclusions` (below) is the following, by the file layout surveyed here: `docs/*.md`, `docs/*.json|yaml|txt`, `docs/chapters/` (31), `docs/npcs/`, `docs/party/` (9), `docs/ensemble/` (765), `docs/archive/` (219), `docs/authority/` (1), plus top-level files. Other wings' sources (`notes/`, `summaries/`, `docs/distill_extractions/`) are nested inside the root source.
- Draft grounding files present under the root wing (verbatim paths):
  - `docs/campaign_state_draft.md`
  - `docs/party_draft.md`
  - `docs/party_draft.candidate.md`
  - `docs/world_state_draft.md`
- The wing named `summaries` (source `summaries`) is pipeline output (per-session dirs holding session-summary.md, review.md, questions.md, VTTs, reports, audio).

`extra_exclusions` (verbatim):
```
temple/
archive/
planning_extractions/
docs/state_extractions/
docs/party_extractions/
docs/planning_extractions/
docs/background/
docs/toee-summary.md
docs/mechanics.md
"*.pdf"
"*.tar.gz"
```

`dispositions` (verbatim, one entry):
```
- divergence: scaffold.nomatch
  kind: deliberate
  rationale: "toee has no docs/chapters, so no narrative wing; the 5-wing wire-what-exists subset (chronicle/prep/notes/summaries/root, root promoted to authoritative canon) is intentional."
  recorded: "2026-07-01"
```
Observation: the rationale says toee has no `docs/chapters`; `docs/chapters/` exists on disk with 31 files (see section 6).

Other mining-related files seen at the campaign root (not interpreted): `.mempalaceignore` (marked "mneme-rendered ... do-not-edit"; its lines include `docs/distill_extractions/`, `notes/sessions/`, `notes/`, `summaries/`, `temple/`, `archive/`, `voice/`, `examples/`, `logs/`, `*.sh`, `.mneme/`), `MEMPALACE.md`, `mempalace.yaml` (root), plus `mempalace.yaml` files inside `notes/sessions/`, `summaries/`, `docs/distill_extractions/` (the last three plus `notes/.mempalaceignore` and `notes/sessions/.mempalaceignore`).

Palace contents not surveyed: no read-only source listing exists until T005.

## 2. Files at each standard kind's usual locations

### npcs
- `docs/npcs/`: 1 file, `docs/npcs/.dedup_state.json`; no subdirectories; no `.md` files.
- Related but elsewhere: `docs/ensemble/merged_dossiers/` (136), `docs/ensemble/state_dossiers/` (142), `docs/archive/npcs/ensemble/` (101), `docs/entity_registry.yaml`, `docs/entity_inventory.md`, `docs/aliases.json`.

### summaries
- `docs/summaries/` (published): **absent**.
- `summaries/` (pipeline output), kept apart:
  - 46 entries at top level: 31 numbered chapter dirs (`001-the-fall-of-the-abbey` ... `031-elemental-management-now-with-more-talking-swords`), 14 dated session dirs (`20260314`, `20260329`, `20260510`, `20260524`, `20260531`, `20260614`, `20260625`, `20260628`, `20260705`, `20260823`, `20260830`, `20260906`, `20261011`, `20261018`), and `mempalace.yaml`.
  - 1319 files in total. By extension: 612 `.mp3`, 415 `.md`, 126 `.json`, 31 `.reviewed`, 30 `.vtt`, 20 `.yaml`, 18 `.prev`, 18 `.log`, 18 `.html`, 7 `.old`, 7 `.cg`.
  - Each of the 31 numbered dirs holds `session-summary.md`, `review.md`, `questions.md`.
  - `session-summary.md` files at depth 2: 42 (`find summaries -mindepth 2 -maxdepth 2 -name session-summary.md | wc -l`).

### grounding
| File | State |
|---|---|
| `docs/world_state.md` | present (443 lines) |
| `docs/campaign_state.md` | present (270 lines) |
| `docs/party.md` | present (203 lines) |
| `docs/planning.md` | present (552 lines) |

### party
- `docs/party.md`: present (also a grounding file, see section 4).
- `docs/party/`: 9 files total
  - `docs/party/calmer.md`, `docs/party/sequioa.md`, `docs/party/zephyr.md`, `docs/party/zinnia.md`
  - `docs/party/rename-files.sh`
  - subdir `docs/party/6/` (4 files): `calmer.md`, `sequioa.md`, `zephyr.md`, `zinnia.md`
- `docs/party_state.md`: absent.
- Per-PC files elsewhere: `voice/calmer_voice.md`, `voice/sequoia_voice.md`, `voice/zephyr_voice.md`, `voice/zinnia_voice.md`; `notes/handouts/20260906-calmer-log.md`, `notes/handouts/20260913-zephyr-log.md`, `notes/handouts/20261018-zinnia-log.md`, `notes/handouts/player_quest_log.md`, `notes/handouts/player_quest_log_calmer.md`, `notes/handouts/08_zinnia_the_biggest_score.md`, `notes/handouts/09_sequoia_the_four_pieces.md`; `config/party.yaml`, `config/players.yaml`.

### prep
- `notes/`: top-level subdirs and file counts: `notes/sessions` 6, `notes/statblocks` 10, `notes/session_prep` 3, `notes/handouts` 15.
- `notes/` top-level files: `area-212-fire-temple-reference.md`, `area-213-water-temple-reference.md`, `falrinth_strategy.md`, `furnishing-the-household.md`, `hedrack_strategy.md`, `hommlet_threats.md`, `lucius_network.md`, `lucius_strategy.md`, `nulb_allies.md`, `nulb_network.md`, `phase3_endgame.md`, `scrub_register_policy.md`, `summary_folder_overlap.md`, `tzgy_scarab_urgent.md`, `upper_temple_network.md`, `vtt_known_additions.md`, `vtt_transcription_corrections.md`; tooling: `extract_proper_nouns.py`, `otter_to_vtt.py`, `proper_nouns_adventure.txt`, `mempalace.yaml`, `.mempalaceignore`, `.scrub_state.json`, `.vtt_spell_pass_state.json`.
- `notes/sessions/` (6 files): `mempalace.yaml`, `nobody-told-nulb.md`, `nulb-knows-now.md`, `the-sleeping-prince.md`, `war-in-the-temple.md`, `.mempalaceignore`.
- `notes/session_prep/` (3 files): `20260906_the_sleeper_in_the_iron_coffin.md`, `20260912_session_2026_09_06.md`, `20261011_dungeon_level_1_notes.md`.
- `notes/` subdirs hold 34 files in total (6 + 10 + 3 + 15).

### docs/distill_extractions/ (today's `chronicle` wing, trust accelerator)
- 30 files: `extract_001.md` ... `extract_029.md` (29) plus `mempalace.yaml`.

## 3. Look-alikes to decide on

Drafts and candidates (`*_draft*`, `*.candidate.*`):
- `docs/campaign_state_draft.md`
- `docs/party_draft.md`
- `docs/party_draft.candidate.md`
- `docs/world_state_draft.md`

Backups (`*.bak`, `*.old`) under `docs/` and `notes/`: none. (`*.old` files exist only under `summaries/`, 7, outside the docs/notes scope: `summaries/20260329/gm-assist-doc.md.old` and six under `summaries/20260614/scene_extractions_new/`.)

Staging/extraction/review dirs under `docs/` and `notes/` (path, file count):
- `docs/distill_extractions/` — 30
- `docs/archive/` — 219
- `docs/archive/distill/state_staging/` — 2 (`campaign_state/extract_001_world_state.md`, `campaign_state/extract_002_threads.md`)
- `docs/archive/distill/state_extractions/` — 29
- `docs/archive/distill/party_extractions/` — 29
- `docs/archive/distill/planning_extractions/` — 58
- `docs/archive/npcs/ensemble/` — 101
- `docs/ensemble/` — 765 (`state_dossiers` 142, `merged_dossiers` 136, `per_chapter` 482, plus `aliases.json`, `exclude_names.md`, `known_names.md`, `merged.json`, `threads.md`)
- `docs/authority/` — 1 (`.lock`, 0 bytes)
- No `reviews/` or `summary_native/` dir under `docs/` or `notes/`.

Outside `docs/` and `notes/` (for reference): `archive/notes/` (1 file, `phase-iii-adapted.md`), `planning_extractions/` (5 files), `summaries/*/scene_extractions*`, `summaries/*/staged_review`, `summaries/*/spell_review`.

## 4. Files that would be shared across kinds

Each needs a `mined_as` choice: ____

- `docs/party.md`: grounding doc and party data. needs a `mined_as` choice
- `docs/party/` (and files in it): reachable as party dir; `docs/party/` is also under the root wing's source. needs a `mined_as` choice if declared under more than one kind
- `notes/sessions/`: nested inside `notes/` (both are existing wings; paths overlap). needs a `mined_as` choice if both are declared
- `notes/handouts/` per-PC logs (`20260906-calmer-log.md`, `20260913-zephyr-log.md`, `20261018-zinnia-log.md`, `player_quest_log*.md`): reachable via `notes/` (prep) and are party-related by name. needs a `mined_as` choice if declared under more than one kind
- `docs/distill_extractions/`: nested inside root wing source `.` as well as its own wing. needs a `mined_as` choice if declared under more than one kind

## 5. Hazards

- Symlinks (`find docs notes summaries voice -type l`): none.
- Gitignored paths (`find docs notes summaries voice -type f | git check-ignore --stdin`): 7 files
  - `notes/.vtt_spell_pass_state.json`
  - `summaries/20260314/GMT20260314-153255_Recording.m4a`
  - `summaries/20260906/GMT20260906-150142_Recording.m4a`
  - `summaries/20261018/GMT20261018-151233_Recording.m4a`
  - `summaries/20260830/GMT20260830-150238_Recording.m4a`
  - `summaries/20260524/zoom_parts/GMT20260524-163415_Recording.m4a`
  - `summaries/20260524/zoom_parts/GMT20260524-153424_Recording.m4a`
  - `.gitignore` also names `docs/background/T1-4_Temple_of_Elemental_Evil_(1e)-notes.pdf`; that file is not present on disk.
- Skip-worktree / sparse (`git -C /home/kostadis/toee ls-files -t toee`): 2826 entries, all `H`; 0 `S` under `toee/`. (The `S` entries, 48509 repo-wide, are in sibling dirs such as `Hillsfar/`, outside this checkout.)
- Non-text extensions under `docs notes summaries voice`: `.m4a` 6 (listed above), `.mp3` 612 (all under `summaries/`, e.g. `summaries/20261011/session-20261011.mp3` and `summaries/20261011/session-20261011.chunks/chunk_NNNNN.mp3`; reproduce with `find summaries -type f -name '*.mp3'`), `.pdf` 0, images 0, archives 0.
- PDFs at the campaign root (outside those paths): `calmer.pdf`, `sequioa.pdf`, `zephyr.pdf`, `zinnia.pdf`. `*.pdf` is in `extra_exclusions`.
- Other: `summaries/` also holds 126 `.json`, 18 `.html`, 31 `.reviewed`, 18 `.prev`, 7 `.cg` files.
- `docs/npcs/.dedup_state.json` is the only file in `docs/npcs/`; `.dedup_state.json` is a line in the root `.mempalaceignore`.

## 6. Candidate campaign kinds

Directories holding material outside the five standard kinds (path, file count):
- `docs/chapters/` — 31 (`chapter_01_the_fall_of_the_abbey.md` ... `chapter_31_elemental_management_now_with_more_talking_swords.md`)
- `docs/distill_extractions/` — 30
- `docs/ensemble/` — 765
- `docs/archive/` — 219
- `docs/background/` — 166 (in `extra_exclusions`; includes module JSON, `*-inventory`-style files)
- `voice/` — 5 (`_genre.md`, `calmer_voice.md`, `sequoia_voice.md`, `zephyr_voice.md`, `zinnia_voice.md`)
- `examples/` — 6
- `temple/` — 788 (`temple/raw` 100, `temple/wiki` 686, plus `purpose.md`, `schema.md`; in `extra_exclusions`)
- `config/` — 8 files (yaml)
- `logs/` — 11
- `notes/statblocks/` — 10
- `notes/handouts/` — 15
- `planning_extractions/` — 5
- `archive/` — 1
- Tracking and registry files: `docs/tracking.txt` (120 lines), `docs/corrections.yaml`, `docs/entity_registry.yaml`, `docs/entity_inventory.md` (964 lines), `docs/aliases.json`, `docs/toee-summary.md` (4624 lines; in `extra_exclusions`), `docs/mechanics.md` (3 lines; in `extra_exclusions`)
- Root files: `MEMPALACE.md`, `mempalace.yaml`, `ui_state.yaml`

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
campaign: toee

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
