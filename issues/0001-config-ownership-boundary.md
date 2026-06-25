# 0001 — Config ownership boundary: `documents` / workspace split

**Status:** open (deferred 2026-06-24)
**Area:** render model · config ownership · T016 (CampaignGenerator)
**Related:** [[hypostasis.yaml]], `campaignlib/config.py`, constitution Principle II (Sovereign
Identity / no Infrastructure Proxy)

## Working principle (the part we DID settle)

A component's configuration splits into two kinds, by one test —
**"does this config item name or reach something *outside* the component?"**

- **External** (names/reaches another service, machine, or shared data root) → **mneme owns it.**
  mneme renders it from `hypostasis.yaml` into a file the component reads. These are the
  Infrastructure-Proxy constants that must never be hardcoded.
- **Internal** (only concerns the component's own behavior) → **the component owns it**,
  hand-edited in its own config.

For CampaignGenerator this sorts cleanly for most keys:

| Key | Owner | Why |
|---|---|---|
| `dgx_endpoint` | mneme (external) | another machine |
| `rpg_library_url` | mneme (external) | the rpg-lib service |
| `fivetools_data_root` | mneme (external) | shared 5etools data tree |
| `system_prompt`, `agents` | CG (internal) | CG's own prompts (pointer + text) |
| `log_dir` | CG (internal) | where CG writes its own logs |

## What's deferred (this issue)

1. **`documents:` is a genuine split.** The *list* of documents to assemble
   (`campaign_state`, `world_state`, …) is CG-internal logic, but the paths resolve against
   the **campaign workspace**, and *which workspace* (`~/campaigns/<x>`) is external binding
   (mneme's `data_roots.campaigns`). Need to decide: does the document list stay CG's while
   only the workspace root comes from mneme? How is the workspace root injected (config key
   vs runtime arg, since it's per-campaign)?
2. **`log_dir` confirmation** — assumed internal; flip only if mneme should ever centralize logs.
3. **Generalization** — confirm the internal/external test holds for the other components
   (e.g. mempalace: storage settings internal, turbovec URL external; rpg-lib: indexing
   settings internal, port external) so the render model is one rule, not per-component.

## Why deferred

The external keys CG needs (`dgx_endpoint`, `rpg_library_url`, `fivetools_data_root`) are
already in `hypostasis.yaml` and are unambiguous, so T016's constant-removal can proceed on those
without resolving the `documents`/workspace edge. This issue tracks the boundary cases so they
get a deliberate decision rather than an accidental one.
