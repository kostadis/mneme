# Contract: the per-campaign mempalace MCP registration (the `mcp` face)

Bring-up renders a `.mcp.json` in the campaign declaring a **mempalace search server pinned to this
campaign's store** (FR-017), so search performed while working in the campaign hits the right palace.
Rendered from the authority's store pointer — **never a hardcoded path** (the CG #112 anti-pattern).

## Rendered shape

`<campaign>/.mcp.json` (project-scoped), a `mempalace` stdio server with the campaign's palace injected:

```json
{
  "mcpServers": {
    "mempalace": {
      "type": "stdio",
      "command": "mempalace-mcp",
      "env": { "MEMPALACE_PALACE_PATH": "<store.path from the authority>" }
    }
  }
}
```

- `command` resolves to the venv's `mempalace-mcp` (verified present at `~/.venvs/main/bin/`).
- The palace is injected via `MEMPALACE_PALACE_PATH` (mempalace's highest-precedence resolver) — value
  comes from the authority's `store.path`. Equivalently a `--palace <alias>` arg; the env form is
  unambiguous and directory-independent.
- The face is **stamped** with the authority hash (coherence — re-rendered if the store pointer changes).

## Invariants

- **No hardcoded store path** — the value always traces to the authority's `store` pointer (kills the
  hardcoded `~/.mempalace/palace` pattern, CG #112).
- The mempalace MCP face targets the **same** store the CLI walk-up resolves to (the `cli_pointer`
  face) — `mneme mp status` asserts they agree (SC-008: right store everywhere).

## Out of scope

- CampaignGenerator's own campaign MCP server and its hardcoded-path bug are the **CG-side** fix
  (CampaignGenerator #112), not rendered here. 003 renders the per-campaign **mempalace** search face.
- A non-MCP search path (HTTP, the turbovecdb service) is GH #20 / turbovecdb#4 — not this feature.
