# Data Model: MCP Face Bound to the Owning mneme (008)

## McpBinding (derived, never stored)

The owning mneme, as the mcp face needs it. Built from the loaded `ConfigEntity`.

| Field | Source | Rule |
|---|---|---|
| `mneme_program` | `entity.venv / "bin" / "mneme"` | absolute; must exist (FR-005) |
| `mempalace_program` | `entity.venv / "bin" / "mempalace-mcp"` | absolute; must exist when a store is declared |
| `config_path` | `entity.source_path` | absolute; must exist |
| `env` | `declared_mcp_env(entity.env)` | existing GH #26 allow-list; `mempalace` entry only |

Construction fails (`McpBindingError`, naming the missing path) instead of falling back to PATH.

## Server entries (mneme-owned keys of `.mcp.json` → `mcpServers`)

See `contracts/mcp-face.md` for the exact JSON. mneme owns exactly two keys, `mneme` and
`mempalace`; every other key is preserved.

## CloneLayout (derived per campaign, read-only)

| Field | Meaning |
|---|---|
| `root` | `ref.tree` when `ref.tree` is set and `ref.path != ref.tree`, else none |
| `campaigns` | sorted names of non-dot, non-symlink child dirs of `root` not in `campaign_shared_dirs` |
| `shared_declared` | whether hypostasis declares `campaign_shared_dirs` |
| `root_has_mneme_entries` | root `.mcp.json` exists, parses, and has a `mneme` or `mempalace` key |

### Verdict (state machine — evaluated, not persisted)

| Condition (first match wins) | Verdict | Root write? | `clone` row |
|---|---|---|---|
| no `root` | `NO_CLONE` | no | (no row) |
| `campaigns` has ≥2 and `root_has_mneme_entries` | `CONFLICT` | **never** | `CLONE_ROOT_CONFLICT` (FAIL) |
| not `shared_declared` | `UNDECLARED` | no | `CLONE_ROOT_OWED` — declare `campaign_shared_dirs` (lists children found) |
| `campaigns` has ≥2 | `MULTI` | no | `CLONE_ROOT_OWED` — root sessions lack this campaign's servers |
| `campaigns == [this campaign]` | `SINGLE` | yes | `CONFORMANT` |

`CONFLICT` is checked before `UNDECLARED` only when the count is possible; with no shared set the
count is unknown, so an undeclared host with root entries reports `UNDECLARED` (to-do) — it cannot
claim a conflict it cannot see (Principle I).

Note: `campaigns` not containing this campaign at all is impossible by construction (the campaign
was discovered as a child of `root`) unless its name is in the shared set — that is a config error
→ `UNDECLARED`-style to-do naming the collision.

## hypostasis.yaml addition

```yaml
campaign_shared_dirs:   # names of non-campaign top-level folders in campaign clones (008)
  - gm-assistant
  - scripts
```

- Parsed into `ConfigEntity.campaign_shared_dirs: tuple[str, ...] | None` (`None` = undeclared,
  distinct from `()` = declared empty).
- Validation: list of plain names (no `/`, not `.`/`..`); else a config problem.

## Status rows

| Row | States | FAIL? |
|---|---|---|
| `faces` (existing) | `CONFORMANT` / `STALE_RENDER` with reasons from `contracts/status-rows.md` | `STALE_RENDER` is FAIL |
| `clone` (new) | `CONFORMANT` / `CLONE_ROOT_OWED` / `CLONE_ROOT_CONFLICT` | only `CLONE_ROOT_CONFLICT` |
