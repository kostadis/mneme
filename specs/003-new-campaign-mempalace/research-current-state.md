# Research: How mempalace is actually configured, set up, and run (current state)

**Date**: 2026-06-26
**Why**: Ground feature 003 (mempalace bring-up for a new campaign) in the real system — the
`kostadis-dev` mempalace fork and the ad-hoc wiring — not in assumptions. Forensic; reflects
**observed** state (Principle I). Several findings overturn the first draft of the 003 spec.

## TL;DR corrections to the first 003 draft

1. **Per-campaign stores ALREADY exist.** The HOWTO's "all campaigns share one `~/.mempalace/palace`"
   is **stale** — that path no longer exists. Reality: `~/.mempalace/palaces/<campaign>/`, one store
   per campaign. So 003 is not "establish per-campaign isolation" / "migrate off a shared store"; it
   is **formalize + de-fragment** an isolation that already exists but is wired inconsistently.
2. **Backend is turbovec, not chroma.** `chroma.sqlite3` files are **dead legacy** from a
   chroma→turbovec migration. Backup/health/restore must be reasoned about for **turbovecdb**.
3. **Backup = preserve the bindings, restore ≠ rebuild.** The expensive asset is the embeddings
   (bindings); restore preserves them; turbovecdb auto-prunes missing entries; full re-embed is
   explicit-only. (Inverts the freshness-gate-then-rebuild model.)

## 1. How mempalace resolves its store (palace) — `~/src/mempalace`, branch `kostadis-dev`, v3.3.5

Palace-path precedence (`config.py`):
1. `MEMPALACE_PALACE_PATH` (or `MEMPAL_PALACE_PATH`) env var.
2. **Walk-up a `mempalace.yaml` with a `palace:` key** from CWD upward.
3. `~/.mempalace/config.json` — a `default_palace` + a `palaces:` **alias→path map**.
4. Default `~/.mempalace/palaces/chat` (a `PalaceNotDeclared` exception path exists; no silent
   fallback in the isolation design, but in practice an undeclared campaign resolves to `chat`).

Also a global `--palace <alias|path>` CLI flag. Relevant env: `MEMPALACE_BACKEND` (=`turbovec`),
`MEMPALACE_EMBEDDING_*`, `MEMPALACE_LLM_*`.

**`init`** writes per-project `mempalace.yaml` (`wing:`/`rooms:`) + `entities.json`; it does **not**
create the store and does **not** overwrite an existing `mempalace.yaml` (the HOWTO "init overwrites"
warning is stale for this version). The store is created on first **`mine`**.

## 2. The store on disk — turbovec, with chroma as dead weight

A live campaign store (`~/.mempalace/palaces/<campaign>/`):

```
turbovec/
  mempalace_drawers/   store.sqlite3   ← durable SOURCE OF TRUTH (holds the bindings/vectors)
                       index.tvim      ← rebuildable turbovec ANN cache (regenerated from store.sqlite3, no re-embed)
  mempalace_closets/   store.sqlite3 + index.tvim
knowledge_graph.sqlite3                ← entity graph
chroma.sqlite3                         ← DEAD LEGACY (chroma→turbovec migration cruft; 48–153 MB)
<uuid>/  .corrupt-…/  .blob_seq_ids_migrated   ← chroma segments + migration markers (dead)
```

- turbovecdb's own docstring (`turbovecdb/collection.py:5-6`): `store.sqlite3` = "durable source of
  truth (WAL)", `index.tvim` = "rebuildable turbovec cache". It carries a generation stamp
  (`store_gen` vs `tvim_gen`, `collection.py:182-183`) — the `.tvim` rebuilds itself when stale,
  **without** re-embedding. This is the derived-vs-authority pattern (Principle V) *inside* the store.
- **Proof chroma is dead:** `obelisk` (newer) has **only** `turbovec/`, no `chroma.sqlite3`; older
  `abyss`/`phandalin`/`toee` still carry 48–153 MB of dead chroma + a `.corrupt-20260615` segment.
- turbovecdb is embedded (`connect(path)`), multi-process safe via `store_gen` (no daemon). The HTTP
  service is a separate, not-yet-first-class feature (kostadis/turbovecdb#4; bring-up = mneme #20).

## 3. The ad-hoc wiring as it actually is

- **Real campaigns live in `~/campaigns/`** (out-of-the-abyss, Phandalin, obelisk, toee, stormgiants,
  Hillsfar, + gm-assistant) — **not** `~/src/campaigns-test` (scratch; its `.mcp.json` points back to
  `~/campaigns/`). 002's fixtures/assumptions used the wrong root.
- **A campaign's mempalace wiring is smeared across THREE places (Fragmented State — Principle V):**
  1. campaign `mempalace.yaml` → `palace:` + `wing:` + `rooms:`
  2. campaign `config.yaml` → a `mempalace:` section (`index_wings`, `canon_wing`) for CG search
  3. **global `~/.mempalace/config.json`** → the `palaces:` alias map + embed/LLM endpoints — a
     **second authority living outside the campaign**.
- **It is inconsistent (verified):**

  | campaign | `mempalace.yaml` | `palace:` | `config.yaml mempalace:` | store on disk |
  |---|---|---|---|---|
  | out-of-the-abyss | ✓ | `abyss` | ✓ | turbovec + dead chroma 153M |
  | Phandalin | ✓ | `phandalin` | ✗ | turbovec + dead chroma 117M |
  | obelisk | ✓ | `obelisk` | ✗ | turbovec only (clean) |
  | toee | ✓ | **MISSING** → resolves to `chat`! | ✗ | turbovec + dead chroma 48M |
  | stormgiants | ✓ | **MISSING** → resolves to `chat`! | ✗ | turbovec |
  | Hillsfar | **no mempalace.yaml** | — | — | — |

- **Search/MCP:** CampaignGenerator exposes search via `MempalaceClient` → `mempalace-mcp` subprocess.
  But `CampaignGenerator/mcp_server.py:391` **hardcodes** `_MP_PALACE_PATH = ~/.mempalace/palace`
  (a dead path) instead of resolving the per-campaign palace → search likely points at nothing.
- **Env/venv:** `MEMPALACE_BACKEND=turbovec` (`~/.bashrc` + Claude Code Stop/PreCompact hooks). Active
  venv `~/.venvs/main/bin/mempalace[-mcp]` (the HOWTO's `worldanvil_pipeline/venv` is stale). Embeddings
  → local Qwen `http://192.168.1.121:8000`; LLM → `http://192.168.1.147:8001` (the DGX/Spark substrate).

## 4. Backup / restore / health — what exists vs must be built

- **No native backup/restore command.** Backups happen only as side effects of `repair` (`palace.backup`)
  and `migrate` (`palace.pre-migrate.<ts>`), plus ad-hoc `.bak` dirs. Real evidence of the intended
  use: `~/.mempalace/backup-preqwen-20260611/` + `palaces.bak-20260611-preqwen/` — snapshots of the
  **old bindings** taken before re-embedding with Qwen (an explicit re-generation event).
- **Backup target (turbovec) = the `turbovec/*/store.sqlite3` files** (the bindings) + `knowledge_graph.sqlite3`.
  **Exclude** `index.tvim` (rebuildable, no re-embed) and dead `chroma.sqlite3`.
- **Restore semantics (decided 2026-06-26):** restore **preserves bindings** as-is by default — never
  auto-rebuild. turbovecdb **auto-prunes** removed entries (`collection.py` `delete`/`_index.remove`),
  so a restored store self-corrects rather than serving stale content. **Full re-embed is explicit
  opt-in only** (e.g., embedding-model swap). This *replaces* the freshness-gate-then-rebuild idea; the
  "no stale False Green" guarantee (Principle I) is met by turbovecdb's auto-prune, not by a rebuild.
- **Store health signal:** chroma's `repair-status` (HNSW divergence) does **not** apply to turbovec;
  turbovec health = `store_gen`/`tvim_gen` consistency + SQLite integrity (needs confirming what
  mempalace's repair surface covers for the turbovec backend).
- **Drift:** `mempalace sync --dry-run` emits a `SyncReport` (scanned/kept/missing/gitignored) and
  detects file *deletion/gitignore*, **not** content change — and it prints a report, **not** the
  `"DRIFT"` token that 002's `runner.is_stale` parses (a 002 bug).

## 5. Implications

**For feature 003 (revise the spec):**
- Reframe from "establish per-campaign stores" → "**formalize + de-fragment** the per-campaign
  mempalace bring-up." Provision the (per-campaign, already-the-model) turbovec store; **render all
  three config faces** (`mempalace.yaml palace:`/`config.yaml mempalace:`/the global `config.json`
  alias) from the single in-campaign authority; first-mine; **back up the bindings**.
- Open architectural question: **where does the palace pointer / alias map live** — promoted into the
  in-campaign authority (Principle V/III), with the global `config.json` rendered from it? (The global
  alias map is today a second authority outside the campaign.)
- Backup/restore per §4 (preserve bindings; turbovecdb auto-prune; re-gen explicit).

**For feature 002 (reconcile / bugs):**
- `.mneme/mempalace.yaml` authority does **not** capture `palace:` or the `config.yaml mempalace:`
  section → it isn't yet the single authority reality requires.
- `runner.is_stale` parses a fictional `"DRIFT"` → wrong against real `mempalace sync`.

**Bugs filed:** CampaignGenerator hardcoded dead palace path; campaign config inconsistency
(missing `palace:` → wrong-palace; Hillsfar no yaml); 002 staleness parsing; 002 authority gap.
**Cruft to clean:** dead `chroma.sqlite3` (~150M × older campaigns) — an observability/cleanup item.
