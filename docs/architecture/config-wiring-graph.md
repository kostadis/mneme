# Configuration & Wiring Graph

> Cross-cutting configuration and the artifacts that wire the tools together, across `mneme`, `CampaignGenerator`, `Mempalace`, and `turbovecdb`.
> Owned here in `mneme` because `mneme` is the source authority that renders the external wiring consumed by the other repos.
> Code-verified: filenames, formats, defaults, and precedence read from source.

## The wiring bridge

`mneme` is the source of truth. Its `hypostasis.yaml` renders CampaignGenerator's external `config/wiring.yaml`, which `resolve_refs` reads as the default for content roots.

```mermaid
flowchart LR
  H["hypostasis.yaml<br/>mneme authority"] -->|mneme renders| W["config/wiring.yaml<br/>external, do-not-edit"]
  W -->|campaignlib.wiring| R["resolve_refs<br/>refs.yaml + refs.local.yaml"]
  R -->|launch_5etools_mcp| RT["5etools runtime<br/>DATA_DIRS to MCP server"]
```

## Config centers

| Center | Owner | Module | Governs |
|---|---|---|---|
| CampaignConfigService | CampaignGenerator | `server/config_service.py` | App/session/UI config (backed by `config_models.py`) |
| server config helpers | CampaignGenerator | `server/config.py` | Derived campaign/session paths, API-key presence |
| campaignlib config | CampaignGenerator | `campaignlib/config.py` | `load_config`, `$VAR` expansion, `find_default_config` |
| MempalaceConfig | Mempalace | `mempalace/config.py` | palace path, backend, embedding, LLM, workers, hooks, chunking |
| hypostasis config | mneme | `hypostasis/config.py` + `models.py` | Host config: machines, services, sources, roots, identity |

## File inventory (verified)

| File | Owner | Format | Location / discovery | Contents |
|---|---|---|---|---|
| `config/wiring.yaml` | CampaignGenerator (rendered by mneme) | YAML, do-not-edit, hash-stamped | explicit → `$MNEME_WIRING` → repo `config/wiring.yaml` → CWD | `fivetools_data_root`, `homebrew_private`, `fivetools_mcp_index`, `rpg_library_url`, `dgx_*`, `pdf_translators` |
| `config.yaml` | CampaignGenerator (hand-edited) | YAML, `$VAR` expanded | CWD → `<repo>/config/config.yaml` | prompts, agents, documents, log_dir, `mempalace.*` |
| `refs.yaml` | CampaignGenerator campaign dir (git-tracked) | YAML | `<campaign-dir>/refs.yaml` | canonical source set + rpglib/homebrew/path refs |
| `refs.local.yaml` | CampaignGenerator campaign dir (git-ignored) | YAML | `<campaign-dir>/refs.local.yaml` | per-machine root dirs |
| `ingest_manifest.yaml` | CampaignGenerator campaign dir | YAML | `<campaign-dir>/ingest_manifest.yaml` | `ingests[]`; palace precedence CLI > manifest > config |
| `~/.5etools-mcp-runtime/<slug>/` | CampaignGenerator (generated) | symlink farm + `.sources.sha256` | `RUNTIME_BASE / slug(campaign_dir)` | built 5etools tree; sha256(refs+local) gates rebuild |
| `~/.mempalace/config.json` | Mempalace | JSON | `~/.mempalace/config.json` | `palace_path`, `palaces` aliases, `default_palace`, `collection_name`, `backend` |
| `mempalace.yaml` | Mempalace (per workspace) | YAML | walk-up from CWD, `palace:` key | active palace for a tree |
| `tunnels.json` / `hallways.json` | Mempalace (per palace) | JSON, 0600 | sibling of palace_path dir | cross-wing/within-wing links |
| `people_map.json` | Mempalace | JSON | `~/.mempalace/people_map.json` | name/alias map |
| `hypostasis.yaml` | mneme (human owns) | YAML, single authority | `$XDG_CONFIG_HOME/hypostasis/hypostasis.yaml` | machines, services, components, data_roots, identity |

## Precedence chains

| Resolves | Order | Code |
|---|---|---|
| CG content roots | `refs.local.yaml` roots → env (`FIVETOOLS_DATA_ROOT`/`RPG_LIBRARY_ROOT`/`HOMEBREW_PRIVATE_ROOT`) → `wiring.yaml` default | `resolve_refs.resolve_roots` |
| Ingest palace | `--palace` → manifest `palace:` → `config.yaml` `mempalace.palace` | `apply_ingest_manifest.resolve_palace` (refuses to guess) |
| Mempalace palace path | `MEMPALACE_PALACE_PATH`/`MEMPAL_PALACE_PATH` → walk-up `mempalace.yaml` → `config.json` `default_palace` → `PalaceNotDeclared` | `MempalaceConfig.resolved_palace_path` |
| Mempalace backend | `config.json backend` → `MEMPALACE_BACKEND` → `chroma` | `MempalaceConfig.backend` |
| Mempalace config values | env → config file → defaults | class docstring |

## Verified defaults

| Setting | Default |
|---|---|
| palace_path | `~/.mempalace/palaces/chat` |
| collection_name | `mempalace_drawers` |
| backend | `chroma` |
| tunnels / hallways | `<palace parent>/tunnels.json`, `<palace parent>/hallways.json` |
| chunking | size 800, overlap 100, min 50 |
| hypostasis path | `~/.config/hypostasis/hypostasis.yaml` |
| 5etools runtime base | `~/.5etools-mcp-runtime/<slug>/` |

## Writers → readers

| File | Writer | Readers |
|---|---|---|
| `config/wiring.yaml` | mneme renders from `hypostasis.yaml` | `campaignlib.wiring` (lru-cached); resolve_refs, launch_5etools_mcp |
| `config.yaml` | human | `campaignlib.load_config`; app + `apply_ingest_manifest` fallback palace |
| `refs.yaml` / `refs.local.yaml` | human (`launch --init-local` seeds local) | `resolve_refs.resolve` → fivetools_ingest, fivetools_catalog, launch |
| `ingest_manifest.yaml` | human | `apply_ingest_manifest` → spawns `fivetools_ingest.py` |
| `~/.mempalace/config.json` | `cli.cmd_init` / `onboarding` / `tool_hook_settings` | mcp_server, palace, searcher, llm_refine, hooks_cli |
| `tunnels.json` / `hallways.json` | `palace_graph._save_tunnels` / `hallways._save_hallways` | mcp_server tools, search neighbor expansion |
| `hypostasis.yaml` | human owns; `ensure_mneme_identity` appends `mneme:` block only | `hypostasis.load/validate` ← mneme cli, lifecycle, mempalace cli/backup |

## Design rules found in code

- `hypostasis.yaml` is the single authority; `FORBIDDEN_TOP_LEVEL` blocks a second writable state store. Identity is appended, never rewritten.
- External vs internal split: `wiring.yaml` (mneme-owned, rendered) holds endpoints/roots; `config.yaml` (hand-edited) holds prompts/agents/docs. `campaignlib.wiring` is the single external accessor.
- Config stays tool-local: CampaignGenerator never imports `MempalaceConfig`; ingest reaches a palace by name/path via the manifest.
- Palace path anchors runtime files: `tunnels.json`/`hallways.json` are per-palace and survive Chroma rebuilds; legacy `~/.mempalace/*.json` only detected, never auto-merged.
- Idempotent, refuse-to-guess: 5etools rebuild gated by sha256(refs+local); palace resolution raises rather than defaulting silently.
