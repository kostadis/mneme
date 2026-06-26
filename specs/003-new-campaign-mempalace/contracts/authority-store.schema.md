# Contract: the store-pointer authority extension + the four rendered faces

Extends the feature-002 authority (`.mneme/mempalace.yaml`). The authority remains the **single
editable source**; everything that names the store is **rendered** from it (FR-015, Principle V).

## Authority extension

```yaml
# .mneme/mempalace.yaml  (002 fields + the new store pointer)
campaign: stormhaven
recipe_version: "1.0.0"
store:                                   # NEW (D1)
  alias: stormhaven                      # palace alias (default = campaign); sanitized
  path: ~/.mempalace/palaces/stormhaven  # dedicated store dir (absolute after expansion)
wings:
  - { name: narrative, source: docs/chapters, trust: authoritative, rooms: [...] }
  - { name: stormhaven, source: ".", trust: reference, rooms: [...] }
# dispositions, extra_exclusions … as in 002
```

**Validation (load-time, all-at-once):** `store.alias` present + sanitized; `store.path` absolute;
exactly one store pointer; bring-up MUST refuse a wings-but-no-store-pointer authority (the
missing-pointer wrong-store bug must be impossible — FR-013/016).

## The four faces rendered from this authority

| Face | Target file | Content |
|---|---|---|
| **cli_pointer** | `<campaign>/mempalace.yaml` | `palace: <alias>`, `wing:`/`rooms:` — so a CLI run *inside the campaign* walks up to this and resolves to the campaign's store (FR-016) |
| **cg_search** | `<campaign>/config.yaml` → `mempalace:` | `index_wings: [...]`, `canon_wing: <...>` derived from the wings (what CG search reads) |
| **global_alias** | `~/.mempalace/config.json` → `palaces:` | this campaign's `alias: path` entry — **read-modify-merge-write**; never overwrite other campaigns' entries |
| **mcp** | `<campaign>/.mcp.json` | a `mempalace` stdio server with the campaign's palace injected — see `mcp-registration.md` |

Each face is **stamped** with the authority hash (reusing 002's render-stamp). `mneme mp status` /
`render --check` flag any face whose stamp no longer matches the authority (coherence — Principle V).

## Invariants

- **No hardcoded store coordinates** in any face — the path/alias always trace to the authority's
  `store` pointer (kills the CG #112 hardcoded-path anti-pattern).
- **global_alias is a merge**, not a clobber — concurrent/other campaigns' entries are preserved (VI).
- A campaign is **never** left without a `palace:` face (the toee/stormgiants wrong-store bug, #21).
