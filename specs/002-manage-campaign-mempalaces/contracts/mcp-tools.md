# Contract: mneme advisory MCP server

`mneme mp mcp` runs an MCP server (official Python SDK / FastMCP — D6) that gives an assistant the inputs to drive **adoption and migration planning** (US5). **Read-only and advisory** (FR-022): no tool mutates campaign data or the index. Every mutation stays in the `mneme mp` CLI behind preview-then-apply, so the server is not a runtime dependency (Principle IV/VI) — if it is down, campaigns still run and the GM can still work via the CLI.

Separate from mempalace's own MCP server (palace search); not a dependency of it.

## Tools

### `get_target_config(campaign: str) -> TargetConfig`  → FR-022

Returns what mneme recommends the campaign adopt: the current recipe resolved against the campaign's existing authority, **preserving non-conflicting choices**, plus a `diff` against the campaign's current config.

```json
{
  "campaign": "out-of-the-abyss",
  "recipe_version": "2.0.0",
  "recommended": { "wings": [ /* CampaignMempalaceConfig shape */ ], "extra_exclusions": [ ] },
  "diff": {
    "added":   [ "mechanical.exclusions.notes/" ],
    "changed": [ ],
    "preserved": [ "wing.abyss.rooms", "wing.narrative" ]
  }
}
```

Reading it changes nothing (advisory until adopted).

### `get_status(campaign?: str) -> ConformanceReport`  → FR-005/008/027

The same honest conformance `mneme mp status` reports, as structured rows: per-campaign `index`/`render`/`recipe` state, each divergence paired with its disposition or marked `undispositioned`. Lets the assistant reason about *what* and *why* before proposing a migration.

### `get_campaign_inventory(campaign: str) -> Inventory`  → US5 (planning input)

The campaign's current document/wing structure, so the assistant can reason about a content-preserving migration:

```json
{
  "campaign": "out-of-the-abyss",
  "wings": [ { "name": "narrative", "source": "docs/chapters", "files": 18 } ],
  "unwinged_docs": [ "campaign_state.md", "world_state.md" ],
  "bible": { "path": "session_summary.md", "lines": 8200, "oversized": true },
  "exclusions_in_effect": [ "summaries/", "logs/" ]
}
```

## On-demand instructions (FR-028/029)

Beyond the data tools above, the server exposes the **instructions** for working with mempalaces as **dynamically loadable capabilities** (MCP prompts and/or resources — the human invokes a prompt; the assistant can also load a resource). This replaces pasting docs into the chat. All read-only.

### `manage_mempalace` — management instructions *(mneme-owned, versioned — FR-029)*

The procedural method for building / configuring / splitting / winging / migrating a campaign mempalace — the `MEMPALACE_HOWTO.md` content, owned by mneme and versioned with the recipe. Loaded to **ground** the assistant's free-form migration reasoning (US5). Exposed as an MCP prompt (e.g. `manage-mempalace`) and as a resource (`mneme://instructions/manage-mempalace@<recipe-version>`).

### `campaign_usage_guide(campaign)` — per-campaign usage guide *(campaign-owned — FR-029)*

How to search/use a specific campaign's palace — wings, trust levels, search patterns, quirks. Served **from the campaign's own `MEMPALACE.md`** (intrinsic state, Principle III); never relocated into mneme. Exposed as a resource (`mneme://campaign/<name>/usage-guide`) and/or a parameterized prompt. Loaded when working in that campaign.

Both are **loaded on demand** — not injected as always-on context — so they cost tokens only when needed (matching mempalace's own load-what-you-need ethos). If the server is down, the GM still works (Principle IV).

### `adopt(campaign: str, confirm: bool = False) -> dict`  → FR-030 (decision 2026-06-26)

The one **write** tool — the chat-driven per-campaign adoption gate. Two-step, mandatory confirm:

- `confirm=False` (default) → **preview only**: returns the target diff (recipe bump, re-rendered
  files, any conflicts) and writes nothing. The assistant surfaces this to the human.
- `confirm=True` → applies the upgrade **into the active checkout** for that one campaign: writes
  the upgraded `.mneme/mempalace.yaml` + re-rendered stamped wing files, and **nothing else**.
  Leaves the change **uncommitted** for the human to review; never auto-commits, pushes, or merges.

Bounded by FR-030: single named campaign, mneme-managed files only (never campaign content),
uncommitted. This is the deliberate, recorded exception to the read-only rule — every *other* write
(publish, bootstrap, migrate, batch adopt) stays off the MCP surface and in the CLI working-copy path.

## Out of scope for the server (deliberately)

No `apply_migration`, `write_authority`, `publish`, `mine`, or batch-write tool. The assistant
produces a `MigrationPlan` (data-model) that the **human approves**; execution is
`mneme mp migrate --plan …` in the CLI, which enforces the verbatim guard (FR-025), write-isolation
(FR-018), and post-migration verification (FR-026). The single sanctioned MCP write is the
confirm-gated, single-campaign `adopt` (FR-030); everything broader stays in the CLI so the human
checkpoint on scope decisions is preserved.
