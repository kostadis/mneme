# Corpus worksheet — toee

- Surveyed path: `/home/kostadis/toee/toee` (sparse git checkout; git root is the parent, `/home/kostadis/toee`)
- HEAD: `8e1f44eb` (`git -C /home/kostadis/toee rev-parse --short HEAD`; `main`, clean). This is the merge of campaigns PR #529 (the summary-native rebuild and grounding publication).
- Date: 2026-10-28
- **Supersedes the 2026-10-23 survey** (HEAD `5961792f`). That survey predates PR #529, so its counts for `docs/npcs/`, `docs/summaries/`, the grounding docs, `summaries/` and the pipeline dirs are stale. Everything below was re-run on 2026-10-28.
- A second, older copy exists at `/home/kostadis/src/campaigns/toee`. It was not surveyed.

Observations only. Nothing here is a decision; the GM writes `.mneme/corpus.yaml`. Section 0 is the conversion path with the lessons from the Phandalin, out-of-the-abyss and obelisk migrations; earlier campaigns' answers appear only as precedent beside a blank for toee.

---

## 0. Conversion path and lessons (2026-10-28)

Phandalin, out-of-the-abyss and obelisk were migrated on 2026-10-25 (obelisk's decisions are in `obelisk.md` section 7). All three ended with `mneme mp status` all ok. Toee's situation resembles obelisk's (an existing v2 authority with a `wings:` block) plus a symlinked grounding store like out-of-the-abyss's.

### 0.1 State of the host today

| Item | Today (2026-10-28) |
|---|---|
| mempalace (`~/src/Mempalace`) | branch `kostadis-dev`, `d23d6a70` (2026-10-24, "Merge pull request #58 from kostadis/fix/57-ollama-sub-batch"). Carries `--skips-json` (#56) and Ollama sub-batching (#57 / PR #58). |
| mneme (`~/src/mneme`) | `main`, `04cdabf` (2026-10-27, PR #78, "arcs becomes a standard kind in recipe v4"). `mneme mp search` (#74) is included. A bare `mempalace search` uses the wrong embedder (#73), so use `mneme mp search` to spot-check. |
| CampaignGenerator (`~/src/CampaignGenerator`) | `main`, `9d4079a` (2026-10-24, PR #594, `canon_wings`). Restart any running CampaignGenerator MCP server or UI after migrating. |
| `~/toee` checkout | `main` at `8e1f44eb`, `git status` clean. Nothing untracked to deal with (obelisk had 48). |

**`data_roots`.** `~/.config/hypostasis/hypostasis.yaml` reads:
```
data_roots:
  fivetools: ~/src/5e-tools-kostadis/data
  campaigns:
    - ~/phandalin
    - ~/out-of-the-abyss
    - ~/obelisk
  mempalace: ~/.mempalace
```
`~/toee` is **not** in `data_roots.campaigns`. `mp adopt` has no `--dir` option, and the other `mp` verbs need either the entry or `--dir ~/toee/toee`. Add `~/toee`: ______

### 0.2 Is there a toee palace on this host?

**No.** The memory note says the palace was rebuilt in 2026-10 as a 5-wing palace; that is not what is on disk now.
- `ls ~/.mempalace/palaces` lists exactly: `chat`, `hallways.json`, `obelisk`, `out_of_the_abyss`, `phandalin`. There is no `toee` directory (`ls ~/.mempalace/palaces/toee`: "No such file or directory").
- `~/.mempalace/config.json` has no line mentioning `toee`.
- `~/toee/toee/.mcp.json` does not exist (and `.mcp.json` is gitignored).

`~/.venvs/main/bin/mneme mp status toee --dir ~/toee/toee` (read-only), verbatim:
```
ok   toee                 recipe  divergent_pending          upgrade available, not yet adopted
todo toee                 corpus  corpus_undeclared          UNDECLARED (owed): wing-model mining is unchanged until the corpus is declared -> mneme corpus init toee
ok   toee                 render  conformant                 derived files coherent
??   toee                 index   index_unverified           unverified: no sync report (No palace found at /home/kostadis/.mempalace/palaces/toee)
ok   toee                 store   missing_config             not provisioned — `mneme mp bringup`
ok   toee                 backup  conformant                 no backup
FAIL toee                 faces   stale_render               global_alias: config.json palaces entry != store path; mcp: .mcp.json missing
??   toee                 gaps    index_unverified           no mine recorded by mneme yet — run `mneme mp refresh toee` to record skipped files
ok   toee                 owner   owned                      owned by this mneme
todo (fleet)              consumers consumers_owed             49 non-compliant consumers (0 partial) -> mneme corpus consumers --noncompliant
```
Owner is `owned` (mneme id `64cf8b36-e823-4b8e-8353-d08fe707f9be`, integrated 2026-07-01). The palace the memory note describes is gone from this host, or lives on another host or path; this survey could not tell which.

**Bringup or regenerate.** The standing GM decision is "migration is a fresh rebuild (`mp regenerate --confirm`), never in-place conversion". Facts for the choice:
- With no palace on this host, both commands build from empty. Obelisk was in this same position and used `bringup`.
- `mp bringup` loads the existing authority, renders all faces (`config.json` palace entry, `.mcp.json`), first-mines through the corpus, and takes a backup. `mp status` already shows `faces FAIL stale_render` for exactly the two things bringup renders.
- `mp regenerate --confirm` validates the corpus, clears the store (nothing to clear), first-mines, and records an empty former-wings record. It does **not** render faces or back up, so it needs `mneme mp render toee` and `mneme mp backup toee` afterwards.
- If a toee palace exists on another host and is copied here before migrating, the trade-off changes; this survey did not see one.

Which one: ______

### 0.3 The authority needs three changes together

`~/toee/toee/.mneme/mempalace.yaml` today has `campaign: toee`, `recipe_version: 2.0.0`, `store.alias: toee`, a `wings:` block (5 wings, section 1), an `extra_exclusions:` list (11 entries) and one `dispositions:` entry. Recipe v2 defines no `kinds:`, so once `corpus.yaml` exists every corpus command refuses with `recipe-no-kinds: recipe v2 defines no kinds; adopt v3 or later`. Today `mp status` already shows `recipe divergent_pending`.

What `authority.validate` (`mneme/mempalace/authority.py`) does once `.mneme/corpus.yaml` exists:
- It refuses `wings:` **and** `extra_exclusions:` with `dual-authority: .mneme/mempalace.yaml has '<key>:' but .mneme/corpus.yaml exists; the corpus file declares the wings, so remove the key`. Both keys must be deleted.
- It does **not** refuse `dispositions:`. Dispositions are still validated if present (kind, rationale for `deliberate`, ISO date), but the toee entry (`scaffold.nomatch`) only matters to the wing-model scaffold check, which is skipped for a corpus campaign (`conform.py`: "a corpus campaign has no wings"). Whether to delete it as stale or leave it is not forced by the validator. Obelisk's finished authority holds only `campaign`, `recipe_version: 4.0.0` and `store.alias`. Delete or keep the disposition: ______
- With no `corpus.yaml`, an authority without wings is also refused (`wings: at least one wing is required`). So **removing `wings:` and writing `corpus.yaml` happen in one sitting**, before any mneme command runs.
- The authority's `campaign:` must equal `corpus.yaml`'s. Keep `campaign: toee` and `store.alias: toee`.

Two ways to get there. Pick one: ______
- **(a) Adopt, then edit.** `mneme mp adopt toee --here` (preview), then `--confirm`, before `corpus.yaml` exists. It moves `recipe_version` to `4.0.0` and re-renders, uncommitted. Then delete `wings:`/`extra_exclusions:` by hand and write `corpus.yaml`. Needs the `data_roots` entry (no `--dir`).
- **(b) Hand edit** (obelisk's choice). In `.mneme/mempalace.yaml`: set `recipe_version: 4.0.0`, delete `wings:` and `extra_exclusions:`, write `corpus.yaml`, all at once. Bringup re-renders afterwards.

### 0.4 Recipe v4 and the standard kinds

`mneme/recipes/mempalace.recipe.v4.yaml` (PR #78, 2026-10-27) defines six standard kinds:

| kind | default trust |
|---|---|
| `npcs` | authoritative |
| `summaries` | authoritative |
| `party` | authoritative |
| `grounding` | authoritative |
| `prep` | reference |
| `arcs` | reference |

`arcs` is new as a standard kind in v4 (GM: "an arc is a story that may or may not turn out"); consumers can name it in `consumers.yaml`. Phandalin and out-of-the-abyss had declared it under `campaign_kinds:`; `mp adopt` moves that declaration to `kinds:`. For a hand edit on a new `corpus.yaml`, declare it under `kinds:` directly. A campaign kind (anything else) must state its `trust`. Kinds with `trust: authoritative` become CampaignGenerator `canon_wings`; `reference` kinds become `index_wings`.

### 0.5 Symlinks: how the resolver treats toee's grounding docs

Facts in the tree (`find docs notes summaries voice -type l -printf '%p -> %l\n'`, 7 symlinks, all under `docs/`):
```
docs/campaign_state.md -> grounding/current/campaign_state.md
docs/canon_events_timeline.md -> grounding/current/canon_events_timeline.md
docs/party.md -> grounding/current/party.md
docs/planning.md -> grounding/current/planning.md
docs/reference -> grounding/current/reference
docs/world_state.md -> grounding/current/world_state.md
docs/grounding/current -> generations/legacy-ac9fa1b72cf24282c8c6/live
```
So the grounding docs are two symlink levels deep. Note there is a **fifth** doc, `docs/canon_events_timeline.md` (516 lines), and a symlinked directory `docs/reference` (8 files: `factions.md items.md locations.md npcs.md party.md threads.md threads_unratified.md threats.md`), exactly like out-of-the-abyss. The generation dir `docs/grounding/generations/legacy-ac9fa1b72cf24282c8c6/` also holds `published/` (a second copy of the docs) and `manifest.json`; `docs/grounding/` also holds `activations/`, `layout.json` and `migrations/`.

**Resolver behaviour** (`mneme/corpus/resolve.py`, read from code, then confirmed by the probe below):
- Symlinks are followed, not skipped (mempalace's own scanner skips symlinks, which is why mneme resolves them first). A declared symlinked file becomes a corpus entry whose **path stays the declared one** and whose `target` is the fully resolved real file inside the campaign. mempalace dedups on that resolved file.
- A symlink that resolves **outside** the campaign is a `symlink-outside` finding. A dangling one is `symlink-not-file`. Neither applies here: all targets are inside `toee/` and exist.
- Symlinked directories are followed during a dir walk (and a declared dir may itself be, or sit under, a link).
- Re-pointing `docs/grounding/current` at a new generation changes what the declared paths resolve to, and `mp refresh` replaces the drawers. That was out-of-the-abyss's recorded GM decision (2026-10-24): declare the stable symlink paths, not a generation path.
- A gitignored target of a symlink that stays in the corpus is a `gitignored` finding; none apply here.

**Probe** (read-only: Python called `mneme.corpus.config.parse` on bytes and `mneme.corpus.resolve.resolve` against `/home/kostadis/toee/toee`; the draft corpora lived only in the process, nothing was written to the campaign; script `/tmp/claude-1000/-home-kostadis-src-mneme/f66d3826-bc57-486c-b0b8-a35dbd70e6c4/scratchpad/probe.py`; recipe v4; git mode `work-tree`). These are **not a proposed corpus**.

| Declaration | Resolved | Findings |
|---|---|---|
| `files:` the 4 `docs/{world_state,campaign_state,party,planning}.md` | 4; each path is the declared symlink, target is `docs/grounding/generations/legacy-ac9fa1b72cf24282c8c6/live/<same>.md` | 0 |
| the same plus `docs/canon_events_timeline.md` | 5, same pattern | 0 |
| `dirs: [docs/grounding/current]` | 13 (the 5 `.md` plus `reference/` 8); paths `docs/grounding/current/...`, target the generation `live/` file | 0 |
| `dirs: [docs/grounding/generations/legacy-ac9fa1b72cf24282c8c6/live]` | 13, plain files (no `target`) | 0 |
| `dirs: [docs/reference]` (symlinked dir) | 8; paths `docs/reference/...`, targets in the generation `live/reference/` | 0 |
| `dirs: [docs/grounding]` | 67 (60 `.md`, 6 `.json`, 1 `.yaml`): the `current` link, `generations/.../published/`, `migrations/`, `activations/` | 0 |
| the 4 docs in `grounding` **and** `dirs: [docs/grounding/current]` in `party` | 17; `ambiguous-mining-kind` on the 4 shared real files ("reachable from kinds [grounding, party] with 0 `mined_as: true` marks; exactly one is required") | 4 |
| the 4 docs and `docs/grounding/current` in the **same** kind | 17 entries (two paths for the shared real files); no finding | 0 |

What that means, precisely:
- **Declaring `docs/world_state.md` etc. (the stable symlinks).** The corpus path is `docs/world_state.md`; the drawer content is the generation's file. A re-point of `docs/grounding/current` changes the content on the next refresh without touching `corpus.yaml`.
- **Declaring `docs/grounding/current/`** reaches the same real files plus `reference/` (8) and `canon_events_timeline.md`, under different corpus paths.
- **Declaring the generation dir** pins the corpus to one generation: after a re-point the declaration still resolves, but to the old generation, and `corpus.yaml` needs editing. It reaches the same real files as the other two.
- **Two paths to one real file in two kinds** (e.g. `grounding` by `docs/world_state.md` and another kind by `docs/grounding/current/`) is a `mined_as` question even though the paths differ, because the shared-file check keys on the resolved file. Two paths in one kind raise no finding.
- `docs/grounding/generations/.../published/` holds a second copy of the same docs (`find docs/grounding/generations -type f | wc -l` gives 27); a `dirs: [docs/grounding]` declaration would include it.

Which paths for the grounding docs (symlinks / `current` / generation dir / other): ______

### 0.6 Other rules that carry over

- **Gitignored means not in the corpus** (#65). A gitignored file found under a declared dir is dropped silently. A gitignored path **named** in `files:` (or a declared dir that is ignored) is a `gitignored` error. On toee, 628 files under `docs notes summaries voice config` are ignored (section 5): 613 session `.mp3` (and `.chunks/`), the `.m4a` recordings, and a few state files. The 2026-10-28 `.gitignore` additions (`summaries/*/*.mp3`, `summaries/*/*.chunks/`) mean `dirs: [summaries]` no longer sweeps in audio. Probe: `dirs: [summaries]` resolves 2138 files of the 2764 on disk.
- **There is no exclude list inside a declared dir.** To keep a subtree out (e.g. `docs/npcs/summary_native/`, 1592 files), list the wanted files under `files:`, as the earlier campaigns did. Here that would mean the 102 top-level `docs/npcs/*.md`: ______
- **A file reachable from two kinds needs `mined_as: true` on exactly one of them** (section 4): ______
- **Trust.** Standard kinds keep their defaults unless overridden; a campaign kind must state its trust.
- **Untracked/dirty files** are not skipped (only gitignored ones are). Toee is clean, so nothing to decide.
- **Large files** (> ~500 KB) among candidate dirs: `docs/ensemble/merged.json` 3,506,456 bytes; `notes/reviews/summary-native-threads-20261026.html` 1,229,295; `notes/reviews/summary-native-npcs-20261026.html` 835,785; `docs/background/adventure-t14-5e.json` 727,020; the four character-sheet PDFs `docs/party/9/*.pdf` (1,660,054 / 947,199 / 939,029 / 844,132); and the `.m4a` recordings (18-83 MB, gitignored). Just under the line: `docs/toee-summary.md` 407,718. Check after the mine whether mempalace skipped any declared one; `mp status` `gaps` lists every skip. Reproduce: `find docs notes summaries voice config -type f -size +500k`
- **CampaignGenerator face** (`config/config.yaml`, mneme#68/#69). Today's `mempalace:` block, verbatim (the rest of the 25-line file is the system prompt, agents and `documents:` paths, which already point at `../docs/grounding/current/*.md`):
  ```
  mempalace:
    canon_wing: toee
    index_wings:
    - chronicle
    - prep
    - notes
    - summaries
  ```
  This is the old singular `canon_wing:` form with the wing-model names. After bringup it must hold `canon_wings:` (the authoritative kinds) and `index_wings:` (the reference kinds) matching `corpus.yaml`. `mp status` does not check this block yet (mneme#69). If stale, run `mneme mp render toee`.
- **Derived files.** Tracked: `.mempalaceignore`, `MEMPALACE.md`, the root `mempalace.yaml` (`palace: toee`, `wing: toee`, mneme stamp), `notes/mempalace.yaml`, `notes/sessions/mempalace.yaml`, `summaries/mempalace.yaml`, `docs/distill_extractions/mempalace.yaml`, `.mneme/mempalace.yaml`, `.mneme/owner.yaml`. Toee's `.gitignore` has `.mcp.json` but no bare `mempalace.yaml` rule. Check after bringup which of the wing-model renders the corpus render rewrote, removed or left, and commit to match. Root `mempalace.yaml`: commit the rewrite, or untrack and add a root-anchored `/mempalace.yaml` ignore rule: ______ (obelisk: commit; out-of-the-abyss and Phandalin: untracked.)
- **Palace name.** `campaign: toee`, `store.alias: toee` gives `~/.mempalace/palaces/toee`. Confirm: ______
- **Gap-finding later.** The `/corpus-gaps` skill lists campaign files that are neither declared nor ruled out, ranked, and writes adds to `corpus.yaml` and outs to `.mneme/corpus.rulings.yaml`.
- **Campaign kinds, as precedent** (not a toee answer): Phandalin `lore` (authoritative) plus `background`, `module`, `prep` (reference); out-of-the-abyss `lore` (authoritative) and `module` (reference); obelisk `chapters` and `module` (both reference). Phandalin and out-of-the-abyss left `docs/chapters` out; obelisk put it in at `reference`. Toee's candidates are in section 6: ______
- **Steps** (assuming `data_roots` has `~/toee`; otherwise `--dir ~/toee/toee`): write the authority change and `corpus.yaml` (0.3) in one sitting; `mneme corpus check toee` until valid; spot-check a kind with `mneme corpus toc toee --kind <kind> --json`; `mneme mp bringup toee --verbose` (or regenerate, then render and backup) and let it run to the end (two lines are normal: "cannot read sources" before the first mine, and `add/upsert with vectors= bypasses the configured embedder`, mempalace#59); check the `config/config.yaml` block; `mneme mp status toee` (expect recipe and corpus conformant, index ok, embedder 1024-dim, faces ok, owner owned); optionally `mneme mp search toee "<an NPC name>" --wing npcs`; commit on a branch through a PR.

---

Counts are files (`find <dir> -type f`) unless stated; they do not follow symlinks unless noted. `git` and `find` commands run from `/home/kostadis/toee/toee`.

## 1. What the palace mines today

Source: `.mneme/mempalace.yaml` (campaign `toee`, `recipe_version: 2.0.0`, `store.alias: toee`). No palace exists on this host (0.2), so "today" means the authority, not a palace listing.

| Wing | source | trust | Flag |
|---|---|---|---|
| `chronicle` | `docs/distill_extractions` | accelerator | |
| `prep` | `notes/sessions` | reference | |
| `notes` | `notes` | reference | |
| `summaries` | `summaries` | reference | |
| `toee` | `.` | **authoritative** | root wing; drops out unless declared |

- The `toee` wing is the root wing (`source: .`) and the only `trust: authoritative` wing. Because it covers the whole checkout, it is the fail-open that mined drafts and pipeline output as canon. Under it (after `extra_exclusions`) fall `docs/*` (including the new `docs/npcs/summary_native/`, `docs/summary_native/`, `docs/reviews/`, `docs/authority/`, `docs/grounding/generations/`), `docs/chapters/`, `docs/ensemble/`, `docs/archive/`, `docs/party/` and `config/`. `logs/`, `voice/` and `examples/` are baseline exclusions.
- Draft grounding files present under the root wing (verbatim paths): `docs/campaign_state_draft.md`, `docs/party_draft.md`, `docs/party_draft.candidate.md`, `docs/world_state_draft.md`.
- Each wing's rooms (omitted here) are generic keyword rooms. Full file: `cat .mneme/mempalace.yaml`.

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
Observation: the rationale says toee has no `docs/chapters`; `docs/chapters/` exists with 31 files (section 6).

Other mining-related files at the campaign root: `.mempalaceignore` (mneme-rendered, stamp `source-sha256: b9a0a6cb…`; its first lines are `logs/ voice/ examples/ .claude/ .mneme/ .mcp.json MEMPALACE.md *.sh config.yaml ui_config.yaml ui_state.yaml`, followed by wing-model lines), `MEMPALACE.md`, `mempalace.yaml`. Reproduce: `cat .mempalaceignore`.

Palace contents not surveyed: there is no palace to list.

## 2. Files at each standard kind's usual locations

### npcs
- `docs/npcs/` total: 1703 files (`find docs/npcs -type f | wc -l`; the resolver agrees for `dirs: [docs/npcs]`).
  - top level: **102 `.md`** published dossiers, plus `.dedup_state.json` and `migration_classification.yaml` (`find docs/npcs -maxdepth 1 -type f`; they begin `air-temple-wraith.md airgid.md albreth.md aldous-glimmerfield.md althea.md`).
  - `docs/npcs/authored/`: 7 `.authored.yaml` (`air-temple-wraith garrick hartsch hedrack romag tharok thorne`).
  - `docs/npcs/summary_native/`: 1592 files (`ch000-041/` 1591: `.md` 1561, `.json` 30; plus `publish_log.json`).
  - `docs/npcs/distilled/`: absent.
- Related elsewhere: `docs/entity_registry.yaml` (114,527 bytes), `docs/entity_inventory.md`, `docs/aliases.json`, `docs/archive/npcs/ensemble/` (101), `docs/ensemble/merged_dossiers/` and `state_dossiers/`, `docs/reviews/npc-review-*` (756 files in three dirs), `notes/reviews/summary-native-npcs-20261026.html`.
- Reproduce: `find docs/npcs -type f | awk -F/ '{print $3}' | sort | uniq -c | sort -rn | head`

### summaries
- `docs/summaries/` (published): **42** `.md` files, no subdirectories (`find docs/summaries -type f | wc -l`), from `000-session-00-the-fall-of-the-abbey.md` to `041-session-41.md` (for example `001-session-01-and-so-it-begins.md`, `040-session-40-beware-the-eastern-tomb.md`). New since the 10-23 survey, when the dir was absent.
- `summaries/` (pipeline output): 2764 files; 56 top-level entries:
  - 42 chapter dirs, `2024-10-12-chapter_00-the-fall-of-the-abbey` through `2026-10-18-chapter_41` (renamed from the old `001-...` names);
  - 12 dated dirs: `20241109 20241122 20241214 20250118 20250330 20250413 20260314 20260524 20260830 20260906 20261018 20261025` (recordings and transcripts; `20261025` holds an `.mp3` and a Zoom `.txt`);
  - `archive/` (33 files, 11 old-named session dirs) and `mempalace.yaml`.
  - By extension: `.json` 778, `.md` 749, `.mp3` 613, `.html` 173, `.vtt` 125, `.txt` 101, `.log` 92, `.yaml` 51, `.reviewed` 31, `.prev` 18, `.m4a` 12, `.old` 7, `.jsonl` 7, `.diff` 3, and one each of `.db`, `.doc`, `.py`.
  - `session-summary.md`: 56 in all; 42 directly under a chapter dir (`find summaries -mindepth 2 -maxdepth 2 -name session-summary.md | wc -l`), 11 one level deeper, 3 two levels deeper. Each chapter dir holds `session-summary.md`, `review.md`, `questions.md`.
  - Audio is gitignored (section 5). Resolver on `dirs: [summaries]`: 2138 files.
- Also pipeline-derived summaries: `docs/summary_native/` (1116 files: `ch000-041` 1007, `ch017-017` 40, `ch023-023` 31, `ch039-039` 38) and `logs/summary-native-full-20261026/` (751).
- Reproduce: `find summaries -type f | wc -l`; `ls summaries`; `find docs/summaries -type f | wc -l`

### grounding
| File | State |
|---|---|
| `docs/world_state.md` | present, **symlink** -> `grounding/current/world_state.md` (219 lines) |
| `docs/campaign_state.md` | present, **symlink** (470 lines) |
| `docs/party.md` | present, **symlink** (129 lines) |
| `docs/planning.md` | present, **symlink** (311 lines) |
| `docs/canon_events_timeline.md` | present, **symlink** (516 lines); a fifth grounding doc, new since 10-23 |
| `docs/reference` | present, **symlink to a directory** -> `grounding/current/reference` (8 files) |

`docs/grounding/` holds 54 files without following links (67 following): `activations/` (1), `generations/legacy-ac9fa1b72cf24282c8c6/{live,published,manifest.json}` (27), `migrations/migration-ac9fa1b72cf24282c8c6/` (originals and displaced copies), `layout.json`, and the symlink `current`. The 10-23 survey's line counts (443/270/203/552) no longer apply. Resolution details: 0.5.

### party
- `docs/party.md`: present (symlink; also a grounding doc, section 4). `docs/reference/party.md` also exists (via the symlinked dir).
- `docs/party/`: 19 files (`find docs/party -type f | wc -l`):
  - top level: `calmer.md sequioa.md zephyr.md zinnia.md rename-files.sh`
  - `docs/party/6/` (4): `calmer.md sequioa.md zephyr.md zinnia.md`
  - `docs/party/9/` (10): 4 character-sheet `.pdf`, `sheets/` (4 `.md`), `indra.md/kostadis1_136526604 (2).md` (a directory named `indra.md`), `sheet_to_md.py`, `__pycache__/sheet_to_md.cpython-314.pyc` (gitignored)
- `docs/party_state.md`: absent.
- Per-PC files elsewhere: `voice/` (5): `_genre.md calmer_voice.md sequoia_voice.md zephyr_voice.md zinnia_voice.md`; `notes/handouts/` (17) per-PC logs; `config/party.yaml`, `config/players.yaml`. Four PDFs at the campaign root (`calmer.pdf sequioa.pdf zephyr.pdf zinnia.pdf`).

### prep
- `notes/` total 682 files (resolver: 681 after ignore). Top-level subdirs and counts: `notes/session_prep` 4, `notes/sessions` 6, `notes/statblocks` 10, `notes/handouts` 17, `notes/reviews` 3, `notes/grounding_refresh` 69, `notes/batch_ch11-23` 369, `notes/batch_ch16-20` 18, `notes/batch_ch24-29` 43, `notes/batch_ch30-35` 19, `notes/batch_early_s2-s8` 96, and `notes/chapter_map_review` (not counted separately).
- `notes/session_prep/` (4): `20260906_the_sleeper_in_the_iron_coffin.md 20260912_session_2026_09_06.md 20261011_dungeon_level_1_notes.md 20261025_session_26.md`.
- `notes/sessions/` (6): `mempalace.yaml nobody-told-nulb.md nulb-knows-now.md the-sleeping-prince.md war-in-the-temple.md .mempalaceignore`.
- `notes/handouts/` (17) includes `20260906-calmer-log.md`, `20260913-zephyr-log.md`, `20261018-zinnia-log.md`, `player_quest_log.md`, `player_quest_log_calmer.md`, `08_zinnia_the_biggest_score.md`, `09_sequoia_the_four_pieces.md`.
- `notes/statblocks/` (10): `139-ghoul-pack.md 140-ghast-lounge.md 141-earth-crypt-necromancer.md 212-temple-of-fire-salamanders.md 213-water-temple-juggernaut.md 219-oohlgrist-troll-chieftain.md belsornig.md fire-temple-salamander-retainer.md frost-brand-area-212.md otis.md`.
- `notes/` top-level files (`find notes -maxdepth 1 -type f`): `area-212-fire-temple-reference.md area-213-water-temple-reference.md chapter_map.json chapter_map.md extract_proper_nouns.py falrinth_strategy.md furnishing-the-household.md hedrack_strategy.md hommlet_threats.md lucius_network.md lucius_strategy.md mempalace.yaml nulb_allies.md nulb_network.md otter_to_vtt.py phase3_endgame.md proper_nouns_adventure.txt renumber_2026-10-25.md scrub_register_policy.md summary_folder_overlap.md tzgy_scarab_urgent.md upper_temple_network.md vtt_known_additions.md vtt_transcription_corrections.md`, plus dotfiles `.mempalaceignore .scrub_state.json .vtt_spell_pass_state.json`.
- Reproduce: `find notes -maxdepth 1 -mindepth 1`; `find notes/<dir> -type f | wc -l`

### arcs
No `docs/arcs/` or `notes/arcs/` exists. Files shaped like arc, thread, tracking or strategy material (found with `find . \( -iname '*arc*' -o -iname '*thread*' -o -iname '*track*' -o -iname '*strateg*' -o -iname '*faction*' -o -iname '*network*' -o -iname '*endgame*' \) -type f`, ignoring pipeline dirs). Observations only:
- `docs/tracking.txt` (120 lines, 6134 bytes; opens "# Main Quests" with a list such as "Clear the Moathouse of evil forces" ... "Confront and defeat Zuggtmoy").
- `notes/` strategy and network files: `falrinth_strategy.md hedrack_strategy.md lucius_strategy.md lucius_network.md nulb_network.md nulb_allies.md upper_temple_network.md hommlet_threats.md phase3_endgame.md tzgy_scarab_urgent.md furnishing-the-household.md`.
- Grounding `reference/threads.md`, `threads_unratified.md`, `factions.md`, `threats.md` (reached through the grounding symlinks, 0.5).
- `notes/reviews/summary-native-threads-20261026.html` (a review page for the threads pass, 1,229,295 bytes).
- `docs/archive/distill/state_staging/campaign_state/extract_002_threads.md` (archive).

### docs/distill_extractions/ (today's `chronicle` wing, trust accelerator)
- 30 files: `extract_001.md` ... `extract_029.md` (29) plus `mempalace.yaml`.

## 3. Look-alikes to decide on

Drafts, candidates, backups, previous versions:
- `*_draft*` under `docs notes summaries`: 4 (`find docs notes summaries -name '*_draft*'`)
  - `docs/campaign_state_draft.md`
  - `docs/party_draft.md`
  - `docs/party_draft.candidate.md`
  - `docs/world_state_draft.md`
- `*.candidate.*`: 10. In `notes/batch_ch11-23/tmp/apply/` (`014b 014 015 016 017 018 024 025 026 .candidate.cleaned.vtt`, 9) and `docs/party_draft.candidate.md`. Also `candidate_plan.json` under `notes/batch_ch11-23/tmp/spell_*` (9) and `notes/batch_early_s2-s8/tmp/spell_candidate.py`.
- Draft material in the new refresh dir: `notes/grounding_refresh/npc-aliases-ch000-041/origin-backups/00-world_state.draft.md`, `01-campaign_state.draft.md`, `02-planning.draft.md`; `notes/grounding_refresh/npc-aliases-ch000-041/candidate/reference/{factions,threads,threads_unratified}.md`.
- `*.proposed.yaml`: 9 in `notes/batch_ch11-23/tmp/apply/`.
- `*.bak`: 0. `*.old`: 7 (all under `summaries/`: `summaries/2026-03-29-chapter_29-opening-battles/gm-assist-doc.md.old` and six under `summaries/2026-06-14-chapter_33-.../scene_extractions_new/`). `*.prev`: 18 and `*.reviewed`: 31 (all under `summaries/*/scene_extractions*`).
- Six `*draft*` names inside `docs/summary_native`, `docs/npcs/summary_native` and `docs/reviews` (`find docs/summary_native docs/npcs/summary_native docs/reviews -iname '*draft*'`).

Staging, extraction, review and pipeline dirs (path, file count):
- `docs/npcs/summary_native/` — 1592; `docs/npcs/authored/` — 7
- `docs/summary_native/` — 1116
- `docs/reviews/` — 757 (`campaign.json` 1; `npc-review-33866336e066` 620; `npc-review-f014daea752f` 94; `npc-review-0197245efd4d` 42)
- `docs/authority/` — 2430 (`events` 114, `snapshots` 2196 `.bin`, `transactions` 119, plus `.lock`)
- `docs/grounding/generations/` — 27; `docs/grounding/migrations/`, `docs/grounding/activations/`
- `docs/distill_extractions/` — 30; `docs/archive/` — 219 (`distill` 118, `npcs` 101); `docs/ensemble/` — 766
- `notes/grounding_refresh/` — 69; `notes/reviews/` — 3; `notes/batch_*` — 545 (369 / 18 / 43 / 19 / 96)
- `summaries/*/scene_extractions*`, `staged_review`, `spell_review`; `summaries/archive/` — 33
- `logs/summary-native-full-20261026/` — 751; `logs/grounding-publication-20261027/` — 32 (`logs/` has 799 files and is a baseline exclusion)
- Outside docs and notes: `planning_extractions/` (5), `archive/` (1), `temple/` (788)

Reproduce: `find docs notes summaries logs \( -iname '*_draft*' -o -iname '*.candidate.*' -o -name '*.bak' -o -name '*.old' -o -name summary_native -o -name reviews -o -name archive -o -name authority -o -name ensemble -o -name grounding_refresh \)`

## 4. Files that would be shared across kinds

Each needs a `mined_as` choice if declared in more than one kind: ______

- `docs/party.md`: grounding doc and party data (symlink to `grounding/current/party.md`). Precedent: Phandalin, out-of-the-abyss and obelisk all declared it in `party` and `grounding`, mined as grounding. Toee: ______
- `docs/reference/party.md` (via the `docs/reference` symlink dir): reachable from a `docs/reference` declaration and from any `docs/grounding/current/reference` declaration (same real file). `mined_as`: ______
- `docs/grounding/current/*` (13 files) are the same real files as `docs/{world_state,campaign_state,party,planning,canon_events_timeline}.md`, `docs/reference/*` and the generation `live/` dir. The probe in 0.5 shows two kinds reaching them without `mined_as` raises `ambiguous-mining-kind`.
- `docs/party/` files are also under the root wing's source; no second standard kind observed.
- `notes/handouts/` per-PC logs (`20260906-calmer-log.md`, `20260913-zephyr-log.md`, `20261018-zinnia-log.md`, `player_quest_log*.md`) are reachable via `notes/` (prep) and are party-related by name.
- `notes/sessions/` is nested inside `notes/` (both are wings today).
- `voice/` is a baseline exclusion in the recipe, but resolves if declared (5 files, probe), as in obelisk's `party`.
- `docs/npcs/summary_native/` sits under a standard-kind dir and shares a name with `docs/summary_native/`; observation only.

## 5. Hazards

- **Symlinks** (`find docs notes summaries voice -type l`): 7, all in `docs/`, listed in 0.5. None in `notes`, `summaries` or `voice` (the 10-23 survey found none at all).
- **Gitignored** (`find docs notes summaries voice config -type f | git check-ignore --stdin`): 628 files.
  - `summaries/2026-10-11-chapter_40-beware-the-eastern-tomb/*.mp3` 612, and its `session-20261011.chunks/` (via `summaries/*/*.chunks/`)
  - `summaries/20261025/*.mp3` 1
  - `.m4a` (12 files, 18-83 MB): `summaries/20241109`, `20241122`, `20241214`, `20250118`, `20250330`, `20250413`, `20260314`, `20260524` (2, under `zoom_parts/`), `20260830`, `20260906`, `20261018`
  - `notes/.vtt_spell_pass_state.json`; `docs/party/9/__pycache__/sheet_to_md.cpython-314.pyc`; `config/refs.local.yaml`
  - Rules: `summaries/*/*.mp3`, `summaries/*/*.chunks/` (added 2026-10-28, "same policy as the .m4a recordings"), `summaries/*/*.m4a`, `*.m4a`, `.mcp.json`, `.mempalace/` (repo-level).
  - The `.zvec-grep/` dir at the campaign root is tool state.
- **Skip-worktree / sparse** (`git -C /home/kostadis/toee ls-files -t toee | awk '{print $1}' | sort | uniq -c`): 11792 entries, all `H`; 0 `S`. Symlink targets are all materialized, so no `not_materialized` paths are expected.
- **Nested git:** none (`find . -name .git -not -path './.git'`).
- **Non-text under `docs notes summaries voice`:** `docs/authority/snapshots/*/*.bin` 2196; `.pdf` 4 (`docs/party/9/*.pdf`); `.db` 1, `.doc` 1 (under `summaries/`); `.m4a` 12 and `.mp3` 613 (gitignored). Four more PDFs at the campaign root. `"*.pdf"` is in today's `extra_exclusions`, which goes away with `wings:`.
- **Large files:** see 0.6.
- **`.dedup_state.json`:** `docs/npcs/.dedup_state.json` (a recipe v4 baseline exclusion at any depth).
- **Directory named like a file:** `docs/party/9/indra.md/` is a directory containing `kostadis1_136526604 (2).md`; a `files:` entry `docs/party/9/indra.md` would be `not-a-file`.
- **File names with spaces and parentheses:** `docs/party/9/kostadis1_136526604 (2).md` and similar (8 files).
- **Tracked derived files:** see 0.6.

## 6. Candidate campaign kinds

Directories holding material outside the standard kinds (path, file count; `find <dir> -type f | wc -l`):
- `docs/chapters/` — 31 (`chapter_01_the_fall_of_the_abbey.md` ... `chapter_31_...`); not a wing today; prose for chapters 1-31 only (the summaries run to 41)
- `docs/distill_extractions/` — 30 (today's `chronicle` wing)
- `docs/ensemble/` — 766; `docs/archive/` — 219
- `docs/background/` — 166 (`.txt` 102, `.json` 52, `.md` 12; in `extra_exclusions`; includes module JSON such as `adventure-t14-5e.json`)
- `docs/reference/` — 8 (symlink dir, 0.5)
- `docs/party/` — 19
- `voice/` — 5; `examples/` — 6; `config/` — 8 (7 resolve; `refs.local.yaml` is ignored)
- `temple/` — 788 (`temple/raw` 100, `temple/wiki` 686, `purpose.md`, `schema.md`; in `extra_exclusions`)
- `logs/` — 799; `planning_extractions/` — 5; `archive/` — 1
- `notes/handouts/` — 17; `notes/statblocks/` — 10; `notes/session_prep/` — 4
- Tracking and registry files directly under `docs/` (bytes): `tracking.txt` 6,134 (120 lines), `corrections.yaml` 3,546, `entity_registry.yaml` 114,527, `entity_inventory.md` 91,651, `aliases.json` 27,578, `authority.yaml` 87,642, `mechanics.md` 86 (in `extra_exclusions`), `toee-summary.md` 407,718 (in `extra_exclusions`)
- Root files: `MEMPALACE.md`, `mempalace.yaml`, `ui_state.yaml`, four `*.pdf`

## 7. GM decisions (2026-10-28)

Every choice below is an explicit GM answer, given in four question rounds on 2026-10-28. `mneme corpus check toee` reports the resulting `.mneme/corpus.yaml` valid: npcs 102, summaries 42, party 26, grounding 13, prep 49, arcs 11.

| Kind | Trust | Files | Decision |
|---|---|---|---|
| `npcs` | authoritative | 102 | Only the top-level `docs/npcs/*.md`, listed under `files:`. Out: `docs/npcs/summary_native/` (1592), `docs/npcs/authored/` (7). |
| `summaries` | authoritative | 42 | `dirs: [docs/summaries]` only. Out: the pipeline `summaries/`. |
| `party` | authoritative | 26 | `dirs: [docs/party, voice]` plus `docs/party.md` (mined as grounding). Includes `docs/party/6/`, `docs/party/9/` (PDFs resolve `minable: false`) and the scripts `rename-files.sh` and `sheet_to_md.py`. |
| `grounding` | authoritative | 13 | The five `docs/*.md` symlinks (`world_state`, `campaign_state`, `party`, `planning`, `canon_events_timeline`) plus `dirs: [docs/reference]`; `mined_as: true` (out-of-the-abyss layout). |
| `prep` | reference | 49 | `dirs: [notes/session_prep, notes/sessions, notes/handouts, notes/statblocks]` plus top-level `notes/area-212-fire-temple-reference.md`, `notes/area-213-water-temple-reference.md`, `notes/furnishing-the-household.md`, `notes/chapter_map.md` and the 10 strategy/network notes; `mined_as: true`. Out: `notes/batch_*`, `notes/grounding_refresh`, `notes/reviews`, the process notes (`renumber_2026-10-25.md`, `scrub_register_policy.md`, `summary_folder_overlap.md`) and the VTT glossaries. |
| `arcs` | reference | 11 | `docs/tracking.txt` plus the 10 strategy/network notes (`falrinth`, `hedrack`, `lucius` strategy; `lucius`, `nulb`, `upper_temple` network; `nulb_allies`, `hommlet_threats`, `phase3_endgame`, `tzgy_scarab_urgent`). Those 10 are in both kinds and are **mined as prep** (GM choice), so the `arcs` wing holds only `tracking.txt`. `corpus toc --kind arcs` still lists all 11. |

Also decided:
- **toee's in-flight work** (summary-native rebuild and grounding publication) was committed first, as campaigns PR #529. Session audio (`summaries/*/*.mp3`, `summaries/*/*.chunks/`) was gitignored and kept on disk, and the run logs and review pages were committed.
- **`data_roots`:** `~/toee` added to `data_roots.campaigns`.
- **Recipe path (0.2):** (b) hand edit: `recipe_version: 4.0.0`, with `wings:`, `extra_exclusions:` and `dispositions:` deleted. The authority is now only `campaign`, `recipe_version` and `store.alias`.
- **Build:** `mneme mp bringup toee`. It built from empty (backup `20261028-034218`), and `mp status` reports all rows ok.
- **No campaign kinds.** Left out: `docs/chapters`, `docs/background` (module), `docs/distill_extractions` (the old `chronicle` wing).
- **Trust:** recipe defaults. Canon wings are `npcs`, `summaries`, `party`, `grounding`. Index wings are `prep`, `arcs`.
- **Renders:** the root `mempalace.yaml` stays tracked, with bringup's rewrite committed. The wing-model renders bringup deleted are committed as deletions. The leftover `notes/.mempalaceignore` and `notes/sessions/.mempalaceignore` were deleted too.
- **Palace name:** `toee`.
- The campaign commit is campaigns PR #530.

The `corpus.yaml` as written to `toee/.mneme/corpus.yaml`:

```yaml
campaign: toee
kinds:
  npcs:
    files:
    - docs/npcs/air-temple-wraith.md
    - docs/npcs/airgid.md
    - docs/npcs/albreth.md
    - docs/npcs/aldous-glimmerfield.md
    - docs/npcs/althea.md
    - docs/npcs/aunt-emma.md
    - docs/npcs/barkinar.md
    - docs/npcs/belsornig.md
    - docs/npcs/black-jay.md
    - docs/npcs/brakka-vusk.md
    - docs/npcs/brask.md
    - docs/npcs/brother-eldin.md
    - docs/npcs/burne.md
    - docs/npcs/captain-dren-halveth.md
    - docs/npcs/captain-gnonsbim.md
    - docs/npcs/captain-marad-vesrek.md
    - docs/npcs/captain-tolub.md
    - docs/npcs/commander-joradin.md
    - docs/npcs/dala.md
    - docs/npcs/davine.md
    - docs/npcs/derrick.md
    - docs/npcs/dick-rentsch.md
    - docs/npcs/eelrich-vane.md
    - docs/npcs/elazar.md
    - docs/npcs/elder-kenter.md
    - docs/npcs/elmo.md
    - docs/npcs/elvanna-thorne.md
    - docs/npcs/eryk-velkori.md
    - docs/npcs/falrinth.md
    - docs/npcs/faria.md
    - docs/npcs/florian.md
    - docs/npcs/furnok-of-ferd.md
    - docs/npcs/garrick.md
    - docs/npcs/glennddarc.md
    - docs/npcs/glennon-clee.md
    - docs/npcs/gonnathrad-kevanarial.md
    - docs/npcs/gremag.md
    - docs/npcs/grindin-well-read.md
    - docs/npcs/grud-squinteye.md
    - docs/npcs/gurdy.md
    - docs/npcs/hartsch.md
    - docs/npcs/hedrack.md
    - docs/npcs/hestort-flintshine.md
    - docs/npcs/horgus.md
    - docs/npcs/ingulf.md
    - docs/npcs/iniri.md
    - docs/npcs/jaroo-ashstaff.md
    - docs/npcs/jarran.md
    - docs/npcs/jerry.md
    - docs/npcs/jijohn.md
    - docs/npcs/jorin-pike-kale.md
    - docs/npcs/kalen.md
    - docs/npcs/keenleene.md
    - docs/npcs/kelno.md
    - docs/npcs/ketta.md
    - docs/npcs/lareth-the-beautiful.md
    - docs/npcs/lenora-glimmerfield.md
    - docs/npcs/lieutenant-krell.md
    - docs/npcs/lodriss.md
    - docs/npcs/lubash.md
    - docs/npcs/lucius-graeme.md
    - docs/npcs/maeris-dorn.md
    - docs/npcs/magda.md
    - docs/npcs/mahoon.md
    - docs/npcs/marek.md
    - docs/npcs/mari-clee.md
    - docs/npcs/mistress-selentis.md
    - docs/npcs/ostler-gundigoot.md
    - docs/npcs/otis.md
    - docs/npcs/pasmarie-clee.md
    - docs/npcs/pearl.md
    - docs/npcs/prefect-alrrem.md
    - docs/npcs/prince-thrommel.md
    - docs/npcs/quinna-poul.md
    - docs/npcs/rannos-davl.md
    - docs/npcs/rithelm-drake.md
    - docs/npcs/robert-deakin.md
    - docs/npcs/romag.md
    - docs/npcs/rufus.md
    - docs/npcs/sarge.md
    - docs/npcs/senshock.md
    - docs/npcs/serena-velkori.md
    - docs/npcs/sister-alina.md
    - docs/npcs/skole.md
    - docs/npcs/snej.md
    - docs/npcs/spugnoir-balkof.md
    - docs/npcs/talla-velkori.md
    - docs/npcs/terjon.md
    - docs/npcs/thalsor-of-the-stone.md
    - docs/npcs/tharok.md
    - docs/npcs/thorne.md
    - docs/npcs/tilly-bizpebble-whistle.md
    - docs/npcs/urot.md
    - docs/npcs/varek-solain.md
    - docs/npcs/verigo.md
    - docs/npcs/vethra-velkori.md
    - docs/npcs/voss.md
    - docs/npcs/vurakhal.md
    - docs/npcs/warda.md
    - docs/npcs/wat.md
    - docs/npcs/y-dey.md
    - docs/npcs/zelt-the-bat.md
  summaries:
    dirs:
    - docs/summaries
  party:
    dirs:
    - docs/party
    - voice
    files:
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
    mined_as: true
  prep:
    dirs:
    - notes/session_prep
    - notes/sessions
    - notes/handouts
    - notes/statblocks
    files:
    - notes/area-212-fire-temple-reference.md
    - notes/area-213-water-temple-reference.md
    - notes/furnishing-the-household.md
    - notes/chapter_map.md
    - notes/falrinth_strategy.md
    - notes/hedrack_strategy.md
    - notes/lucius_strategy.md
    - notes/lucius_network.md
    - notes/nulb_network.md
    - notes/nulb_allies.md
    - notes/upper_temple_network.md
    - notes/hommlet_threats.md
    - notes/phase3_endgame.md
    - notes/tzgy_scarab_urgent.md
    mined_as: true
  arcs:
    files:
    - docs/tracking.txt
    - notes/falrinth_strategy.md
    - notes/hedrack_strategy.md
    - notes/lucius_strategy.md
    - notes/lucius_network.md
    - notes/nulb_network.md
    - notes/nulb_allies.md
    - notes/upper_temple_network.md
    - notes/hommlet_threats.md
    - notes/phase3_endgame.md
    - notes/tzgy_scarab_urgent.md
```
