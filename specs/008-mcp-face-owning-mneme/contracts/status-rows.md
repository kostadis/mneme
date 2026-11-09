# Contract: status rows (008)

## `faces` row — new mismatch reasons

Added to `faces_coherent`'s list (joined with `; ` into the row note, state `STALE_RENDER`).
`<where>` is `.mcp.json` for the campaign file and `root .mcp.json` for the clone-root file.

| Reason text | When |
|---|---|
| `mcp: <where> missing` | file absent (existing text for the campaign file) |
| `mcp: <where> unreadable` | not valid JSON / not an object |
| `mcp: <where> has no mneme server` | `mneme` key absent |
| `mcp: <where> mneme command != <expected>` | command differs from the binding |
| `mcp: <where> mneme config != <expected>` | `--config` arg absent or differs |
| `mcp: cannot bind owning mneme: <error>` | the owning mneme's programs/config cannot be located |
| `mcp: <where> has no mempalace server` | store declared, `mempalace` key absent |
| `mcp: <where> mempalace command != <expected>` | includes today's bare `mempalace-mcp` |
| `mcp: <where> mempalace palace != store path` | existing |
| `mcp: <where> embedder/backend env out of date (...)` | existing |

The root file is checked only in verdict `SINGLE`. The `faces` row is emitted for every
non-FOREIGN campaign with an authority, store or not. The note for a coherent campaign stays
`right store everywhere` (`mneme server bound` when the campaign has no store); the fix hint appended to a stale row is `— run \`mneme mp faces <name>\``.

## `clone` row (new)

Emitted only for campaigns with a clone root and OWNED by this mneme.

| State | FAIL | Note |
|---|---|---|
| `conformant` | no | `single-campaign clone <root>` |
| `clone_root_owed` | no (to-do) | `campaign_shared_dirs not declared in hypostasis.yaml — clone <root> holds: a, b, c` |
| `clone_root_owed` | no (to-do) | `clone <root> holds N campaigns (a, b) — sessions opened at the root will not have this campaign's servers` |
| `clone_root_conflict` | **yes** | `MISCONFIGURED: clone <root> holds N campaigns (a, b) but root .mcp.json has mneme-owned entries (mneme, mempalace) — nothing changed; see kostadis/campaigns#672` |

`clone_root_conflict` is in `FAIL_STATES`; `clone_root_owed` is not (like `consumers_owed`).

## MCP server

`mneme mp mcp`'s `get_status` returns these rows unchanged (it already serializes conformance
rows); no new tool.
