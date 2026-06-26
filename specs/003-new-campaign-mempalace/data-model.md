# Data Model: Mempalace Bring-Up for a New Campaign (Phase 1)

Extends the feature-002 entities (`mneme/mempalace/models.py`). Authority = editable truth in the
campaign; everything else is derived/stamped or observed. Frozen dataclasses, no I/O.

---

## StorePointer *(authority — new field on the 002 authority, D1)*

Added to `CampaignMempalaceConfig`. The campaign's declaration of its dedicated store — the single
source from which all four faces render.

| Field | Type | Notes |
|---|---|---|
| `alias` | str | the palace alias (defaults to the campaign name) |
| `path` | Path | the dedicated store dir (default `~/.mempalace/palaces/<campaign>`) |

**Validation**: `alias` non-empty + sanitized (mempalace's wing/alias rule); `path` absolute; one
store pointer per campaign. A campaign authority with wings but **no** store pointer is invalid for
bring-up (the missing-pointer bug must be impossible — FR-013/016).

---

## RenderedFace *(derived — the four faces, D1)*

A render target produced from the authority + store pointer, stamped with the authority hash (reuses
002's `RenderedArtifact`/stamp). Coherence-checked by status.

| Face | Target | Render rule |
|---|---|---|
| `cli_pointer` | `<campaign>/mempalace.yaml` | `palace: <alias>` + `wing:`/`rooms:` (drives walk-up — FR-016) |
| `cg_search` | `<campaign>/config.yaml` (`mempalace:` section) | `index_wings`, `canon_wing` from the authority's wings |
| `global_alias` | `~/.mempalace/config.json` (`palaces:` map) | **read-modify-merge-write** this campaign's `alias→path`; never clobber other entries; re-stamp |
| `mcp` | `<campaign>/.mcp.json` (a `mempalace` server) | stdio `mempalace-mcp` with the campaign's palace injected (env/arg) — never hardcoded (FR-017) |

**Coherence rule (Principle V)**: each face carries (or is checked against) the authority hash; a
face whose stamp no longer matches the authority is flagged by status. The `global_alias` face is a
**merge** into a shared file — the render reads current `config.json`, sets only this campaign's key,
re-writes (other campaigns' entries preserved — VI).

---

## DedicatedStore *(observed — D2/D6)*

The campaign's turbovec store on disk. Derived/rebuildable; never an authority.

| Field | Type | Notes |
|---|---|---|
| `path` | Path | `~/.mempalace/palaces/<campaign>/` |
| `present` | bool | the dir + `turbovec/<collection>/store.sqlite3` exist |
| `bindings_files` | tuple[Path,...] | `turbovec/*/store.sqlite3` + `knowledge_graph.sqlite3` (the backup set) |
| `rebuildable_files` | tuple[Path,...] | `index.tvim` (regenerated from bindings, no re-embed) |
| `legacy_files` | tuple[Path,...] | `chroma.sqlite3` + chroma segments (dead; ignored/cleanable) |

---

## StoreHealth *(observed — D5/D6)*

| Field | Type | Notes |
|---|---|---|
| `present` | bool | store exists |
| `consistent` | bool | turbovec `store_gen`/`tvim_gen` coherence + SQLite integrity |
| `state` | `healthy \| degraded \| missing` | drives the `mneme up` gate (D5) and status (IX) |
| `note` | str | observed detail |

`mneme up` **fails** unless `state == healthy` (FR-010).

---

## BindingsBackup *(derived/disposable — D3)*

A snapshot of the bindings, labeled non-authoritative.

| Field | Type | Notes |
|---|---|---|
| `campaign` | str | |
| `location` | Path | under the configured backups dir (not the campaigns repo) |
| `taken` | str (ISO) | stamped after the run (date passed in, not generated in-process) |
| `contents` | tuple[Path,...] | the `store.sqlite3` set + `knowledge_graph.sqlite3` (no `index.tvim`/chroma) |

**Restore** copies `contents` back; turbovecdb rebuilds the index + auto-prunes (no re-embed).
**Regenerate** is a separate explicit re-`mine` (re-embed) — not modeled as a backup op.

---

## BringUpStep / BringUpReport *(observed — IX)*

The observability surface for the operation (Principle IX — report each step + owed follow-up).

**BringUpStep**: `name` ∈ `configure` · `render_faces` · `provision` · `first_mine` · `backup`,
`state` ∈ `ok \| skipped \| failed`, `observed` (str), `note` (str).

**BringUpReport**: `campaign`, `tuple[BringUpStep,...]`, `owed` (tuple[str,...] — follow-ups, e.g.
"review the starter wings"), and an `exit_code` (0 iff no step failed). An interrupted bring-up is
**never** reported ready (FR-008): a failed/missing step ⇒ non-ready.

---

## Relationships

```text
CampaignMempalaceConfig (authority, in campaign)          ← THE source (V/III)
  + StorePointer ───────────────────────────────────────────────┐
        │ render (stamped, coherent)                             │
        ▼                                                        │
  RenderedFace × 4:  cli_pointer · cg_search · global_alias(merge) · mcp
        │ (cli_pointer + global_alias) point mempalace at →      │
        ▼                                                        │
  DedicatedStore (~/.mempalace/palaces/<campaign>)  ── first mine ──▶ bindings (store.sqlite3 = truth)
        │ observe                          back up │                 index.tvim (rebuildable, no re-embed)
        ▼                                          ▼
  StoreHealth ──▶ mneme up gate (D5) + status      BindingsBackup ──restore──▶ copy back; turbovecdb rebuilds + prunes
        │
        ▼
  BringUpReport ──▶ honest step-by-step + owed follow-up (IX)
```
