# Contract: bindings backup / restore / regenerate (turbovec)

The index is **derived** (re-mineable), but the **bindings** (computed embeddings) are an expensive
asset. Backup preserves them; restore brings them back without re-embedding; re-generation (re-embed)
is a separate explicit verb. (FR-011/012; turbovec layout per [research-current-state.md](../research-current-state.md).)

## What is the backup set

For a store at `~/.mempalace/palaces/<campaign>/`:

| Include (the bindings = truth) | Exclude |
|---|---|
| `turbovec/<collection>/store.sqlite3` (every collection: `mempalace_drawers`, `mempalace_closets`, …) | `turbovec/<collection>/index.tvim` — rebuildable from `store.sqlite3`, no re-embed |
| `knowledge_graph.sqlite3` | `chroma.sqlite3` + `<uuid>/` segments + `.corrupt-*` — **dead legacy**, never backed up |

## `backup`

- Copy the include-set to `<backups>/<campaign>/<stamp>/`, preserving the `turbovec/<collection>/`
  layout. Label it derived/disposable (a marker file). `<backups>` is **not** the campaigns repo.
- The copy MUST be a consistent snapshot — coordinate with turbovecdb's store lock / WAL checkpoint
  (build-time detail, D3) so `store.sqlite3` isn't copied mid-write.

## `restore`

- Copy the backup set back into the store dir (replacing `store.sqlite3` + `knowledge_graph.sqlite3`).
- **Do not** restore `index.tvim` — on next mempalace open, turbovecdb rebuilds it from the restored
  `store.sqlite3` (`tvim_gen` vs `store_gen`), **without re-embedding**, and **auto-prunes** entries
  whose source is gone. Restore therefore preserves bindings and self-corrects.
- Report: bindings preserved; any entries pruned by reconciliation. **Never** silently re-generate.

## `regenerate`

- The **only** re-embed path: a full `mempalace mine` from scratch into the store (after clearing it),
  for a deliberate event (e.g., embedding-model change). Requires explicit `--confirm`. Independent of
  backup/restore.

## Invariants

- Restore **never** re-embeds (FR-012); regenerate is the only embed-from-scratch path.
- Backups are **non-authoritative** (Principle IV): the ground truth is always the documents +
  configuration; a backup just preserves the expensive bindings. SC-007 (delete store → re-bringup
  reproduces) holds independently of any backup.
