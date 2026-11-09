# Contract: the mcp face (008)

## Files

| File | Written when |
|---|---|
| `<campaign>/.mcp.json` | campaign is OWNED by the rendering mneme |
| `<clone root>/.mcp.json` | additionally, when the clone verdict is `SINGLE` (data-model.md) |

Both are host-local and git-ignored. Same content rules for both.

## Entries mneme owns

```json
{
  "mcpServers": {
    "mneme": {
      "type": "stdio",
      "command": "<venv>/bin/mneme",
      "args": ["mp", "mcp", "--config", "<abs path of hypostasis.yaml>"]
    },
    "mempalace": {
      "type": "stdio",
      "command": "<venv>/bin/mempalace-mcp",
      "env": {
        "MEMPALACE_PALACE_PATH": "<store path>",
        "...": "allow-listed MEMPALACE_* from hypostasis env (GH #26)"
      }
    }
  }
}
```

Rules:

1. `command` values are absolute and must exist at render time; otherwise render raises and
   writes nothing (neither file).
2. `mneme` has no `env` key. `mempalace.env` contains only `MCP_ENV_ALLOW` keys.
3. `mneme` is written even with no store; `mempalace` only when the authority has a store.
   With no store, an existing `mempalace` key is left as-is (not deleted, not checked).
4. All other keys in `mcpServers`, and all top-level keys other than `mcpServers`, are preserved
   with their values unchanged.
5. A file that exists but is not a JSON object → render raises, file untouched.
6. Write is atomic (temp file in the same directory + replace).
7. In verdict `CONFLICT`, `MULTI`, `UNDECLARED`, the clone-root file is never opened for writing.

## Who renders

- `mneme mp faces <campaign>` and bring-up's `render_faces` step.
- Both refuse (no writes) unless the campaign is OWNED by the loaded mneme identity.
- `mp refresh` does not render faces.

## `mp faces` output

Unchanged format (`rendered <path>` per file). The clone-root file appears as an extra
`rendered <root>/.mcp.json` line in verdict `SINGLE`. In other verdicts a line
`skipped <root>/.mcp.json: <verdict reason>` is printed (stdout, exit 0), so the GM sees why.
