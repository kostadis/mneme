# Contract: `mneme mp` bring-up commands (+ the `mneme up` gate)

Extends the feature-002 `mneme mp` group. Exit codes as in 002 (`0` OK / `1` runtime / `2` config).
Greenfield: these operate on a campaign with no prior mempalace setup; the existing fleet is the
migration's job (GH #24).

---

### `mneme mp bringup CAMPAIGN [--dry-run] [--no-backup] [--config PATH]`  → US1/US2 (FR-001..006, FR-016/017)

The one-shot bring-up: **configure → render faces → provision → first-mine → back up → report.**

- **configure**: bootstrap the single authority (002) for the campaign + write its **store pointer**
  (alias=campaign, path=`~/.mempalace/palaces/<campaign>`).
- **render faces**: render all four (D1) from the authority — `mempalace.yaml` `palace:`/wings, the
  `config.yaml mempalace:` section, the global `config.json` alias (**merge**), the `.mcp.json`
  mempalace server. Creation-time writes go directly into the campaign workspace (FR-005).
- **provision + first-mine**: `mempalace mine --palace <alias>` (per wing, sub-scopes-before-root),
  which creates the store.
- **back up**: snapshot the bindings (D3) unless `--no-backup`.
- Output: a **BringUpReport** — per-step observed outcome + any owed follow-up (IX). Exit 0 iff no
  step failed; an interrupted run reports **not-ready**, never ready (FR-008).
- `--dry-run`: show the planned steps + the faces that would be written; provision/mine/backup nothing.
- Idempotent: re-running on an already-brought-up healthy campaign is a no-op / reported repair (FR-008).
- A campaign with **no documents** → configures + provisions, reports "nothing to index yet" (not a failure).

---

### `mneme mp backup CAMPAIGN [--config PATH]`  → US3 (FR-011)

Snapshot the **bindings** (`turbovec/*/store.sqlite3` + `knowledge_graph.sqlite3`) to the backups
location, labeled derived/disposable. Excludes `index.tvim` (rebuildable) and `chroma.sqlite3` (dead).

### `mneme mp restore CAMPAIGN [--from BACKUP] [--config PATH]`  → US3 (FR-012)

Copy the bindings back into the store. **Preserves bindings — never re-embeds.** On next open
turbovecdb rebuilds `index.tvim` and auto-prunes removed entries. Reports that bindings were preserved
(and any pruning). Refuses to silently re-generate.

### `mneme mp regenerate CAMPAIGN [--confirm] [--config PATH]`  → US3 (FR-012, explicit re-embed)

The **only** path that re-embeds: a full `mine` from scratch (e.g., embedding-model change). Requires
`--confirm` (it's expensive). Distinct from restore.

---

### `mneme mp status` — additions  → US2/US5 (FR-006, SC-008, IX)

`status` (002) gains, per campaign: **store** state (built/stale/missing via D6), **backup** state
(present? when?), and **right-store** checks — the rendered `palace:` resolves to the campaign's store
and the `.mcp.json` mempalace face targets the same store (flag any wrong-store resolution). A
just-brought-up campaign shows built/conformant, never `missing_config`.

---

### `mneme up CAMPAIGN` — store-health gate  → US4 (FR-010/014)

`mneme up` brings up the campaign **runtime** and now **health-gates the mempalace store** first: if
the store is missing/unhealthy (D6), it **fails** (exit 1) with a clear "not brought up — run `mneme
mp bringup`" message. It does **not** bring the store up itself.
