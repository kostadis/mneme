# Implementation Plan: Manage Campaign Mempalaces

**Branch**: `002-manage-campaign-mempalaces` | **Date**: 2026-06-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-manage-campaign-mempalaces/spec.md`

## Summary

Give `mneme` a second job. Today `mneme up/down` runs CampaignGenerator for one campaign; this feature makes `mneme` **manage the per-campaign mempalaces** — the semantic indexes each campaign keeps over its adventure documents — without ever deciding a campaign's content or editing the GM's live checkout.

The architecture is a direct application of the existing `hypostasis` pattern (single authority → stamped, derived renders → honest observed status), re-pointed at campaigns:

- **One authority per campaign, stored in the campaign** — a single `.mneme/mempalace.yaml` holds that campaign's choices (wings, room/keyword routing, exclusions, indexing order) **plus** the recorded *dispositions* (why this campaign diverges, if it does). The per-wing `mempalace.yaml` files and `.mempalaceignore` that `mempalace` consumes become **derived, stamped renders** of that one authority — never a second place to edit (Principle V). A one-time migration consolidates today's scattered files into it (FR-017).
- **A mneme-owned recipe** — the shared best practice, versioned in the `mneme` package: a *mechanical* layer (baseline exclusions, "mine sub-scopes before root," tunnel room-naming, the `init`-overwrites-config hazard) that is *enforced* as conformance, and a *recommended scaffold* (the 3-wing narrative/chronicle/`<campaign>` pattern) that a campaign may override (FR-007, FR-015).
- **Honest cross-campaign status** — `mneme mp status` reports *observed* state per campaign (built / stale / missing-config / divergent), reading the silicon: render-stamp coherence, and `mempalace`'s own source-vs-index drift signal (so mneme stores **no** index metadata of its own — no horcrux). Every divergence is paired with its recorded disposition, or flagged **undispositioned — needs a decision** (FR-005, FR-027).
- **Refresh = orchestrate `mempalace mine`** per wing in the correct order, from each campaign's own authority, subprocess-only (loose coupling, Principle VII) (FR-003/004).
- **Propagate by publishing, adopt per-campaign** — `publish` renders a recipe upgrade for every campaign into mneme's **private working copy** of the campaigns repo and pushes a proposal branch; it never touches an active checkout (FR-018). Each campaign **adopts manually** on its own side — the load-bearing Gate 2 (FR-021).
- **Adoption may require migration**, and the migration plan is **reasoned out freely by an assistant** through mneme's **advisory MCP server** (which serves the per-campaign *target config* and inventory, and — on demand — the **management instructions** and the campaign's **usage guide**, so the assistant loads the *method* instead of the human pasting docs), then **human-approved** before execution. Three mechanical invariants make free reasoning safe regardless of the plan: content stays **verbatim** (FR-025), writes stay in the working copy (FR-018), and mneme **verifies the actual resulting index** afterward (FR-026).

## Technical Context

**Language/Version**: Python 3.11+ (matches the existing `hypostasis`/`mneme` package and the all-Python component ecosystem).

**Primary Dependencies**: standard-library-first, reusing what 001 already pulls in — `PyYAML` (authority + recipe), `jinja2` + the existing `render.py` stamping pattern (derived wing configs), `typer` (CLI). New: the official **MCP Python SDK** (`mcp`, FastMCP) for mneme's advisory server (mempalace ships its own separate stdio server — not a dependency); `git` via subprocess for the private working copy. `mempalace` itself is invoked **only** as a subprocess (`mempalace mine|status|sync|split`), resolved from the venv exactly as `lifecycle.py` resolves CG's `start`. No new database.

**Storage**:
- *Authority* — `.mneme/mempalace.yaml` per campaign, **in the campaign repo** (the one editable store; carries wings + dispositions).
- *Derived* — per-wing `mempalace.yaml` + `.mempalaceignore`, rendered and **stamped** with the authority+recipe hash (coherence-checked, never hand-edited).
- *Recipe* — `mneme/recipes/mempalace.recipe.<ver>.yaml`, **mneme-owned**, versioned in the package.
- *Index* — `~/.mempalace/...`, owned by `mempalace`. mneme keeps **no** index metadata (staleness is read from `mempalace`, not stored — Principle III/IV).

**Testing**: `pytest`. Unit: authority load/validate, render golden-files (authority → wing yaml + ignore, stamped), conformance + disposition classification (deliberate/pending/undispositioned), target-config resolution, the verbatim guard. Integration: `discover → render → refresh` over a temp campaigns tree with a **stub `mempalace`** binary; `publish` against a temp git repo proving the active checkout is byte-unchanged (SC-009); honest `status` over mixed-state fixtures (the 5 real campaigns are the shape: one full, one ignore-only, three bare).

**Target Platform**: Linux / WSL2 (dev box). Campaigns live in a Git repo (`github.com/kostadis/campaigns`); the local active checkout is resolved via `data_roots.campaigns` (reads) and a separate mneme-managed clone is used for writes.

**Project Type**: Single project — extends the existing `mneme/` CLI package with a `mneme mp` command group and an MCP server. Edits no other repo's code; it *writes campaign data* only through its private working copy.

**Performance Goals**: not a hot path. `status` answers in a few seconds across all campaigns; `refresh`/`mine` is bounded by `mempalace`. No throughput targets.

**Constraints**: never write an active checkout (writes go to the private working copy → repo); `mempalace` is touched only via subprocess (Principle VII/VIII); one authority per campaign (Principle V); deterministic paths (render/conform/refresh/publish) carry **no** LLM; the LLM appears **only** in the human-approved migration-planning step, fenced by the three invariants above.

**Scale/Scope**: ~5–10 campaigns, one operator; each campaign has 1–3 wings and tens-to-hundreds of documents.

### Decisions ratified for this plan (detail in [research.md](./research.md))

1. **mempalace invocation** → **subprocess CLI only** (`mempalace mine|status|sync|split`), never an internal import (Principle VII/VIII; mirrors `lifecycle.py`).
2. **Staleness signal** → read from **`mempalace sync --dry-run`/`status`** (source-vs-index drift), so mneme stores no index metadata of its own (Principle III/IV — no horcrux).
3. **Per-campaign authority** → a single `.mneme/mempalace.yaml` in the campaign; wing `mempalace.yaml` + `.mempalaceignore` are **stamped renders** of it (reuse 001's `render.py` hash-stamp mechanism). Consolidated by a one-time `migrate`/`bootstrap`.
4. **Publish/adopt carrier** → mneme pushes a **proposal branch** to the campaigns repo from its private working copy; **adoption is the campaign owner merging/pulling** (manual Gate 2). Opening a PR via `gh` is an optional convenience, not required.
5. **MCP server** → official **MCP Python SDK (FastMCP)**, **advisory/read-only** tools (`get_target_config`, `get_status`, `get_campaign_inventory`) **plus on-demand instructions** (D8): a mneme-owned `manage_mempalace` method (versioned with the recipe) and a per-campaign `campaign_usage_guide` served from the campaign's `MEMPALACE.md`. All mutation stays in the CLI behind preview-then-apply, so the server is not a runtime dependency (Principle IV/VI).
6. **Migration planning** → **free-form, assistant-authored, human-approved** (FR-024), deliberately departing from "LLM renders only"; made safe by verbatim (FR-025) + write-isolation (FR-018) + post-migration verification (FR-026). Recorded as a Complexity-Tracking deviation below.

## Constitution Check

*GATE: must pass before Phase 0. Re-checked after Phase 1 design (below).*

| Principle | Gate | This plan |
|---|---|---|
| I — Silicon Truth | status reports observed, never declared | ✅ `mp status` reads render-stamp coherence + `mempalace`'s own source-vs-index drift; never echoes the authority. A divergence is reported with its disposition, or as "undispositioned — needs a decision" (FR-005/008/026/027). |
| II — Sovereign Identity / no Infra Proxy | no hardcoded paths/coordinates in logic | ✅ campaign locations from `data_roots.campaigns`; wing source dirs from the authority; recipe names *meanings* ("the narrative wing"), not paths. |
| III — Intrinsic State / no Horcruxes | state travels with its entity; nothing hand-synced | ✅ authority **and dispositions** live in the campaign and move with it; mneme stores no index metadata (staleness derived from `mempalace`). |
| IV — Manager is a Transient Viewer | wipe mneme, point at campaigns, reconcile | ✅ Brick Test: per-campaign config + dispositions survive a mneme wipe (FR-011); the recipe is versioned package code (reconstructable); the MCP server is advisory — campaigns run without it. |
| V — One Entity, One DB / no stale copies | one authority; coherent derived copies | ✅ `.mneme/mempalace.yaml` is the sole editable store per campaign; wing yamls + ignore are stamped renders, coherence-checked and regenerated, never a second authority (FR-016); writes converge through the working copy → repo, never a private edit path. |
| VI — Federated Authority, input[∞] | per-entity, degrade independently | ✅ discover/status/refresh/publish operate per-campaign; a missing/invalid campaign FAILs alone (FR-006); campaigns adopt independently at their own pace (FR-021). |
| VII — Logical Datasets / low coupling | consume meanings; render, don't import | ✅ render into `mempalace`'s native per-wing config; `mempalace` invoked by subprocess, never imported; `mempalace` stays ignorant of mneme. |
| VIII — Transform the Constraint | simpler coordinate before complexity | ✅ propagation reuses **git** (branch + manual merge) instead of a new sync daemon/DB; adoption gate is a merge, not a workflow engine; staleness reuses `mempalace`'s signal instead of a new metadata store. |

**Anti-patterns checked:** Optimistic Lies (status reads silicon + disposition, never guesses intent — avoided); Infrastructure Proxy (paths externalized to authority/config — avoided); Fragmented State (one authority per campaign; renders consolidated — avoided); Split-Brain (no second editable store; mneme never edits the active checkout, so no merge-conflict-by-construction — avoided).

**One deviation, justified below** (free-form LLM migration planning) → see Complexity Tracking. No other unjustified violations → **GATE PASS**.

## Project Structure

### Documentation (this feature)

```text
specs/002-manage-campaign-mempalaces/
├── plan.md              # This file
├── research.md          # Phase 0 — the 6 ratified decisions + rationale
├── data-model.md        # Phase 1 — authority / recipe / disposition / target / migration entities
├── quickstart.md        # Phase 1 — runnable validation scenarios (maps to SC-001..012)
├── contracts/
│   ├── cli.md                       # `mneme mp` command contract (status/refresh/render/publish/adopt/bootstrap)
│   ├── campaign-authority.schema.md # `.mneme/mempalace.yaml` — the single per-campaign authority
│   ├── recipe.schema.md             # the mneme-owned recipe (mechanical + scaffold), versioned
│   └── mcp-tools.md                 # advisory MCP tool contract (get_target_config / get_status / get_campaign_inventory)
├── checklists/
│   └── requirements.md  # spec quality checklist (already complete)
└── tasks.md             # Phase 2 — /speckit-tasks (NOT created here)
```

### Source Code (repository root)

```text
mneme/                      # existing CLI package (the transient manager)
├── cli.py                  # + register the `mp` command group
├── lifecycle.py            # (unchanged) up/down
├── mempalace/              # NEW — the campaign-mempalace manager
│   ├── __init__.py
│   ├── discover.py         # enumerate campaigns under data_roots.campaigns; detect authority presence
│   ├── authority.py        # load + validate `.mneme/mempalace.yaml` (the single authority + dispositions)
│   ├── recipe.py           # load the mneme-owned versioned recipe (mechanical + scaffold)
│   ├── render.py           # authority → stamped wing mempalace.yaml + .mempalaceignore (reuses hypostasis render-stamp)
│   ├── conform.py          # observed-vs-recipe conformance + disposition classification → report rows
│   ├── refresh.py          # orchestrate `mempalace mine` per wing in sub-scopes-before-root order (subprocess)
│   ├── target.py           # compute the recommended target config (recipe resolved for a campaign)
│   ├── workcopy.py         # private working-copy clone/commit/push of the campaigns repo (proposal branch)
│   └── migrate.py          # adoption/migration execution: preview → apply (working copy) → verbatim guard → verify
├── mcp/                    # NEW — mneme's advisory MCP server
│   ├── __init__.py
│   └── server.py           # FastMCP tools: get_target_config, get_status, get_campaign_inventory
└── recipes/
    └── mempalace.recipe.v1.yaml   # the mneme-owned recipe (FR-015) — the shared best practice

tests/
├── unit/                   # authority validate, render golden-files, conform/disposition, verbatim guard, target
└── integration/            # discover→render→refresh (stub mempalace); publish on temp git (active checkout unchanged); honest status

# Campaign data (written ONLY via the private working copy, never the active checkout):
#   github.com/kostadis/campaigns  →  each campaign gains `.mneme/mempalace.yaml` (authority)
#   and stamped wing `mempalace.yaml` + `.mempalaceignore` (derived)
```

**Structure Decision**: Single-project CLI, extending `mneme/`. The new `mneme/mempalace/` subpackage is the manager surface; `mneme/mcp/` is the advisory server; `mneme/recipes/` holds the one mneme-owned shared artifact. Everything else authoritative lives **in the campaigns repo**, not here — the manager stays transient (IV). Reuses 001's `render.py` stamping wholesale rather than inventing a new coherence mechanism (VIII).

## Complexity Tracking

> One deliberate deviation from the constitution's "Determinism is Trust" / "human owns structure, LLM renders" stance, plus two recorded design choices.

| Choice | Why needed | Simpler/other alternative rejected because |
|---|---|---|
| **Free-form, LLM-authored migration plan** (FR-024) — the assistant reasons out the per-campaign migration rather than mneme emitting a deterministic transform | A mempalace's structure must serve *this* campaign's needs (US5) — it is genuine judgment (what wing serves what retrieval), not a mechanical mapping. A fixed template would force a one-size structure the spec explicitly rejects (FR-007 scaffold is a *recommendation*). | Made safe without determinism by relocating the checkpoint: **human approval is mandatory** before execution, and three invariants hold regardless of the plan — content stays **verbatim** (FR-025, plan literally cannot rewrite prose), writes stay in the **working copy** (FR-018, blast radius bounded), and mneme **verifies the actual index** afterward (FR-026, catches an approved-but-wrong plan). The LLM gets latitude only on structure; integrity is mechanically guaranteed. |
| **A new MCP server in mneme** | The adoption workflow is conversational (US5); the assistant needs the target config + inventory programmatically (FR-022). | Kept from becoming a runtime dependency (IV/VI): tools are **advisory/read-only**; every mutation stays in the CLI behind preview-then-apply. If the server is down, campaigns still run and the GM still works. |
| **A private working copy (second clone) of the campaigns repo** | The hard requirement that mneme never edit the GM's active checkout (FR-018, SC-009) | A direct edit of the active checkout is exactly the Split-Brain/surprise-merge this forbids; a clone is the minimal way to write "through version control" while leaving the live tree untouched. The clone holds no authority — it is a staging viewer, discardable and re-cloneable (IV). |
