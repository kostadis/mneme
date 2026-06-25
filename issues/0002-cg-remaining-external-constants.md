# 0002 — CG: remaining external constants (SC-002 tail)

**Status:** resolved 2026-06-24 (all sites externalized in T016; see resolution at bottom)
**Area:** T016 (CampaignGenerator) · SC-002 grep-clean · render model
**Related:** [[0001-config-ownership-boundary]], `hypostasis.yaml`, T020 (turbovecdb), T036 (rpg-lib)

## Context

T016's first pass externalized the **core infra constants** in CG's main CLI tools using
the internal/external model + `campaignlib.wiring` (rendered `config/wiring.yaml`):
DGX endpoint + DGX model (`extract_facts`, `backends`), 5etools data root
(`fivetools_catalog`, `fivetools_ingest`, `resolve_refs`), rpg-lib URL (`mcp_server`,
`rpg_retriever`). External keys were removed from `config/config.yaml`.

CG turned out **larger than T016's 5-constant description**. SC-002 ("the constants appear
only in config/templates, zero in logic") is **not yet fully grep-clean** — this tracks the
tail, because several items need a decision rather than a mechanical repoint.

## Remaining real (non-docstring) sites

| Site | Constant | Notes / decision needed |
|---|---|---|
| `query_rpg_lib.py:32` | `DEFAULT_RPGLIB_DIR = ~/src/mytools/rpg-lib` | Used for a **`sys.path` import** of rpg-lib modules **and** to locate `rpg_library.db`. rpg-lib is now pip-installed (T036) → drop the sys.path hack, import directly. The **DB location is data-plane** (out of config scope) — needs its own treatment. (Decision 2's "module invocation" premise was wrong: it's an import, not a subprocess.) |
| `fivetools_ingest.py:74-75` | `_DEFAULT_RPGLIB_DB` (`…/rpg-lib/rpg_library.db`), `_DEFAULT_PDF_TRANSLATORS` (`…/pdf-translators`) | DB path = data-plane; pdf-translators dir = another external repo path not in `hypostasis.yaml`. |
| `resolve_refs.py:43` | `homebrew_private = ~/src/homebrew-private` | Another shared external data root — add to `hypostasis.yaml` `data_roots`? |
| `server/routers/scene_editor.py:627` | `… or "http://localhost:8000"` | DGX-endpoint fallback in the **web server** (its own `CONFIG`); wire to `wiring_get` in the server context. |
| `launch_5etools_mcp.py:52` | `DEFAULT_MCP_INDEX = ~/src/5etools-kostadis/mcp/index.js` | The 5etools MCP index path — external; add a key to `hypostasis.yaml` (sibling of `data_roots.fivetools`)? |

Docstring/help-text mentions (e.g. `ensemble.py:23`, `apply_ingest_manifest.py:15`,
`fivetools_copy.py:20`) are **left as-is** per the agreed decision (SC-002 targets logic
defaults, not documentation).

## To resolve

1. **hypostasis.yaml additions** for the genuinely-external-but-unmodeled roots: `homebrew_private`,
   the 5etools MCP index, possibly `pdf-translators`. Decide which become `data_roots` entries.
2. **Data-plane line** for `rpg_library.db` — referenced by location, not owned (per the
   established config-vs-data boundary). Where does its path live?
3. **query_rpg_lib** — remove the rpg-lib `sys.path` hack (use the installed package); decide
   how it locates the DB.
4. **Web-server wiring** — `scene_editor.py` should read external config via `campaignlib.wiring`
   like the CLI tools.

Until then, SC-002 is **partially** satisfied: the core infra constants are externalized in the
primary tools; this tail is tracked, not silently dropped.

## Resolution (2026-06-24)

All sites externalized in T016. `hypostasis.yaml` `data_roots` gained `homebrew`,
`fivetools_mcp_index`, `pdf_translators`, and `rpg_library_db` (location referenced — contents
stay data-plane), exposed via the CG wiring template. Repointed: `resolve_refs` (homebrew),
`fivetools_ingest` (rpg DB + pdf-translators), `launch_5etools_mcp` (MCP index),
`scene_editor` (web-server DGX fallback → `wiring_get`). `query_rpg_lib` had real surgery: the
rpg-lib `sys.path` import hack is **removed** (it imports the installed `library_api` directly),
`--rpglib-dir` dropped, and `--db` now defaults to wiring `rpg_library_db`.

SC-002 is now **grep-clean across CG logic** — the only remaining matches are docstring/help-text
examples, left per the agreed decision. CG suite: 913/914 pass (the 1 failure is an unrelated
live-mempalace test needing a seeded palace, not a T016 regression).
