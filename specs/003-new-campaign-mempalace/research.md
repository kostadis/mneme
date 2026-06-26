# Research: Mempalace Bring-Up for a New Campaign (Phase 0)

The big scope forks were resolved in the spec; the *current-state* facts are verified in
[research-current-state.md](./research-current-state.md). This file records the technical decisions
for building bring-up on the real mempalace/turbovecdb surfaces. Decision / Rationale / Alternatives.

---

## D1 — The store pointer lives in the authority; four faces render from it

**Decision**: Extend the 002 authority (`.mneme/mempalace.yaml`) with a **store pointer**
(`store: { alias: <campaign>, path: ~/.mempalace/palaces/<campaign> }`). Bring-up renders four derived
faces from the authority, all stamped/coherent (reusing the 002 render-stamp):
1. the campaign `mempalace.yaml` `palace: <alias>` + `wing:`/`rooms:` (drives CLI walk-up — D7);
2. the campaign `config.yaml` `mempalace:` section (`index_wings`, `canon_wing`) for CG search;
3. the campaign's entry in the global `~/.mempalace/config.json` `palaces:` map — by **read-modify-merge-write** (never clobber other campaigns; re-stamp);
4. the per-campaign `.mcp.json` mempalace server (D4).

**Rationale**: FR-015 (authority is the single source; everything that names the store is rendered —
Principle V/III). Reusing 002's stamp gives coherence/drift detection for free across all four faces.

**Alternatives**: store pointer only in the global `config.json` — rejected (second authority outside
the campaign, the current Fragmented State). Overwrite `config.json` wholesale on render — rejected
(clobbers other campaigns — VI); must merge.

---

## D2 — Provision = declare + render + first-mine (let mempalace create the store)

**Decision**: To provision a dedicated store, bring-up (a) renders the alias into `config.json` + the
`palace:` face, then (b) runs the **first `mempalace mine --palace <alias>`**, which creates
`~/.mempalace/palaces/<campaign>/turbovec/<collection>/{store.sqlite3,index.tvim}`. mneme never
formats/initializes a store itself.

**Rationale**: verified — `mempalace mine` creates the store on first run; the palace path resolves
from the rendered pointer. Lowest coupling (Principle VIII/VII): mneme points, mempalace builds.

**Alternatives**: mneme initializes a turbovec store via `turbovecdb` directly — rejected (imports a
churning backend; duplicates mempalace's creation logic). `mempalace init` to pre-create — partially
used (it writes `mempalace.yaml`/`entities.json`) but it does **not** create the store and won't
overwrite our rendered `mempalace.yaml`; the store still comes from `mine`.

---

## D3 — Backup preserves the bindings; restore copies them back; re-embed is explicit

**Decision**:
- **Backup** = copy the turbovec **`store.sqlite3`** files (per collection) + `knowledge_graph.sqlite3`
  to a labeled, derived/disposable backup dir. **Exclude** `index.tvim` (rebuildable) and
  `chroma.sqlite3` + chroma segments (dead legacy).
- **Restore** = copy those files back into the store dir. On next open, turbovecdb rebuilds
  `index.tvim` from `store.sqlite3` (the `tvim_gen` vs `store_gen` check — **no re-embed**) and
  auto-prunes entries whose source is gone (`collection.py` `delete`/`_index.remove`).
- **Regenerate** (`mneme mp regenerate`) = the explicit, opt-in re-embed: a full `mine` from scratch
  (e.g., embedding-model change). Never automatic.

**Rationale**: FR-011/012 (preserve bindings; turbovecdb self-heals; re-embed explicit). The bindings
(`store.sqlite3`) are the expensive asset; `index.tvim` regenerates locally without embed calls. The
"no stale False Green" guarantee (I) is met by turbovecdb's auto-prune, not a rebuild gate (VIII).

**Alternatives**: back up the whole palace dir incl. `index.tvim`/`chroma.sqlite3` — rejected (bloat;
backs up dead + rebuildable bytes). A freshness-stamp-then-rebuild restore — rejected (the
preserve-bindings decision; turbovecdb already reconciles). **Open implementation detail** (non-blocking):
whether `store.sqlite3` must be copied under a write-lock / WAL-checkpointed for a consistent snapshot
— confirm turbovecdb's lock (`~/.mempalace/locks/`) usage at build time.

---

## D4 — Per-campaign MCP face = a rendered `.mcp.json` mempalace server, palace injected

**Decision**: Render a `.mcp.json` in the campaign declaring a `mempalace` **stdio** server that runs
`mempalace-mcp` (from the venv) with the campaign's palace injected — `env: { MEMPALACE_PALACE_PATH:
<path> }` (or `--palace <alias>` arg), and/or the campaign dir as cwd so walk-up resolves. The path
comes from the authority's store pointer; it is **never hardcoded**.

**Rationale**: FR-017 — search-in-campaign hits the right store; rendered from the one authority and
coherent with it. Directly avoids the CG #112 anti-pattern (a hardcoded dead palace path). Verified:
`mempalace-mcp` exists in `~/.venvs/main/bin`; palace resolves from `MEMPALACE_PALACE_PATH`.

**Alternatives**: rely on CampaignGenerator's existing `mcp_server.py` for mempalace search — rejected
(it hardcodes the dead `~/.mempalace/palace`, CG #112; and it is CG's, not the per-campaign mempalace
search FR-017 asks for). **Open detail**: whether to also reconcile/replace the existing CG campaign
server entry is out of scope here (CG #112 is the CG-side fix); 003 renders the mempalace face.

---

## D5 — `mneme up` store-health gate (observed; fails, never brings up)

**Decision**: Extend `mneme/lifecycle.up()` with a **store-health gate**: before starting the campaign
runtime, check (observed) that the campaign's mempalace store is present and healthy; **fail** if not
(it does not bring it up — FR-010/014). The check reuses the existing substrate-gate shape
(`unreachable_deps`-style): a per-campaign predicate over the store.

**Rationale**: Principle I + FR-010 — don't run the runtime against a not-brought-up store; surface it
(IX) rather than proceed silently. Mirrors the existing DGX/rpg-lib gate.

**Alternatives**: `mneme up` performs bring-up if missing — rejected by the spec (FR-014; keeps heavy
one-time work out of the per-start path). Warn-but-proceed — rejected (Optimistic Lie).

---

## D6 — Store-health signal for turbovec

**Decision**: Health = (a) the store dir + `turbovec/<collection>/store.sqlite3` exist, and (b) a
turbovec-native consistency signal — `store_gen` vs `tvim_gen` coherence and SQLite integrity —
surfaced via a subprocess `mempalace status --palace <x>` (and/or a small read-only check). Chroma's
`repair-status`/HNSW-divergence does **not** apply.

**Rationale**: verified — turbovec health is the generation-stamp + SQLite integrity model, not
chroma's HNSW. Feeds the up-gate (D5) and `mneme mp status` (IX).

**Alternatives**: reuse chroma `repair-status` — rejected (wrong backend). **Open detail** (non-blocking):
confirm exactly what `mempalace status` reports for a turbovec palace, or whether a tiny turbovecdb
read-only open is needed; resolve against the installed pin at build.

**Note (relates to #22):** 002's `runner.is_stale` parses a fictional `"DRIFT"` from `sync --dry-run`.
003 does **not** depend on that; "freshness" here is turbovecdb's job (auto-prune) and health is D6.
Fixing #22 is tracked separately.

---

## D7 — Directory-context CLI resolution falls out of the rendered `palace:` face

**Decision**: FR-016 ("from inside the campaign dir, the CLI uses that campaign's store") is satisfied
by rendering the campaign `mempalace.yaml` `palace:` key (face 1, D1). mempalace's resolution
walks up from CWD to a `mempalace.yaml` with a `palace:` key. Bring-up guarantees the key is present
and correct; a campaign is never left pointer-less.

**Rationale**: verified resolution precedence (env → walk-up `palace:` → global `config.json` →
default `chat`). The current bug (toee/stormgiants missing `palace:` → resolve to `chat`) is exactly a
missing face-1 render; bring-up renders it, so directory-context resolution "just works."

**Alternatives**: require `MEMPALACE_PALACE_PATH` env per shell — rejected (operator memory; not
directory-contextual; opacity). Rely on the global `config.json` `default_palace` — rejected (that's
the wrong-store bug).

---

## Resolved unknowns

All Technical-Context unknowns resolved above. Non-blocking build-time confirmations (none change the
architecture): the exact consistent-snapshot procedure for copying `store.sqlite3` (D3 lock/WAL), the
precise `mempalace status` output for a turbovec palace (D6), and the exact `.mcp.json` server spec
mempalace-mcp expects (D4) — each verified against the installed `kostadis-dev` pin during implementation.
