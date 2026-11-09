# Quickstart: validating 008

Run from the worktree (`~/src/mneme-008`) with its own venv or `uv run`. Unit tests use temp
dirs and a fake venv; nothing below touches a real campaign until step 4.

## 1. Gates

```bash
ruff check .
pytest -q tests/unit
```

## 2. Unit scenarios the tests must cover (by story)

| Story | Scenario | Expect |
|---|---|---|
| US1 | render for OWNED campaign | `mneme` entry with abs command + `--config <abs>`; other keys preserved |
| US1 | campaign with no store | `mneme` entry written; no `mempalace` added |
| US1 | FOREIGN campaign (owned by another mneme) | `mp faces` refuses, nothing written (UNINTEGRATED is rendered — research R2) |
| US2 | decoy `mempalace-mcp` first on PATH | entry names `<venv>/bin/mempalace-mcp` |
| US2 | venv lacks `mempalace-mcp` | render raises naming it; neither file changed |
| US3 | delete `mneme` key / bare `mempalace-mcp` / wrong `--config` | `faces` row STALE_RENDER with the matching reason |
| US3 | fresh render | `faces` row conformant |
| US4 | single-campaign clone, shared set declared | root `.mcp.json` written; `clone` conformant |
| US4 | two campaigns, root has no mneme keys | root untouched; `clone_root_owed` |
| US4 | two campaigns, root has `mneme` key | root byte-identical after `mp faces`; `clone_root_conflict` (FAIL) |
| US4 | shared set undeclared | root untouched; `clone_root_owed` listing children |
| edge | invalid JSON in either file | render raises, file untouched; status `unreadable` |
| edge | two mnemes (two configs/venvs), one campaign each | each file names only its owner |

## 3. Declare the shared set on this host (GM step)

The GM adds to `~/.config/hypostasis/hypostasis.yaml` (`statblocks` was removed from `~/obelisk`
by the GM on 2026-11-09, so it is not listed):

```yaml
campaign_shared_dirs: [gm-assistant, scripts]
```

## 4. Live check on this host (after merge + install into `~/.venvs/main`)

```bash
mneme mp status | grep -E ' (faces|clone) '      # before: faces flags bare mempalace-mcp / no mneme
for c in Phandalin out-of-the-abyss obelisk toee greenwold; do mneme mp faces "$c"; done
mneme mp status | grep -E ' (faces|clone) '      # after: all conformant (SC-001)
jq '.mcpServers | keys' ~/toee/.mcp.json ~/toee/toee/.mcp.json
```

Expected: both toee files list `mneme` and `mempalace` alongside their existing servers;
`~/obelisk/.mcp.json`'s hand-added `mneme` entry is replaced with the rendered one.
All five campaigns are OWNED on this host (verified 2026-11-09).

Then open a session in `~/toee` and call the `mneme` server's `get_status` for `toee` (SC-005).

## 5. Conflict check (SC-006), in a scratch clone only

Make a throwaway sparse clone with two campaigns and a rendered root, run `mp status`: the
`clone` row is FAIL and `sha256sum <root>/.mcp.json` is unchanged after `mp faces`.
