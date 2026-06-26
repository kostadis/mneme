# Data Model: Manage Campaign Mempalaces (Phase 1)

In-memory entities (frozen dataclasses, mirroring `hypostasis/models.py`). **Authority** = editable source of truth, stored in the campaign. **Derived** = regenerated, stamped, never hand-edited. mneme holds no authoritative state of its own.

---

## Recipe *(mneme-owned, versioned — D4)*

The shared best practice. Read-only at runtime; lives in `mneme/recipes/`.

| Field | Type | Notes |
|---|---|---|
| `version` | str (semver) | stamped into renders; compared in conformance ("upgrade available") |
| `mechanical` | `MechanicalRules` | the **enforced** layer |
| `scaffold` | `Scaffold` | the **recommended**, overridable layer (FR-007) |

**MechanicalRules**: `baseline_exclusions: tuple[str,...]` (always-ignore globs), `mining_order: "subscopes_before_root"`, `tunnel_rooms: tuple[str,...]` (e.g. `("npcs","world")` — shared names that create cross-wing tunnels), `hazards: tuple[str,...]` (documented, e.g. "init overwrites root mempalace.yaml").

**Scaffold**: `recommended_wings: tuple[WingTemplate,...]` for the 3-wing / 2-wing / 1-wing patterns; each `WingTemplate` carries a wing name + suggested rooms. Advisory only.

**Validation**: `version` is valid semver; mechanical rules non-empty.

---

## CampaignMempalaceConfig *(authority — `.mneme/mempalace.yaml`, in the campaign — D3)*

The **one editable store** per campaign (FR-002/016).

| Field | Type | Notes |
|---|---|---|
| `campaign` | str | campaign name (matches workspace dir) |
| `wings` | tuple[`Wing`,...] | the campaign's chosen wings (its content decision — FR-020) |
| `extra_exclusions` | tuple[str,...] | campaign-specific ignores, merged over the recipe baseline |
| `recipe_version` | str | the recipe version this campaign has adopted/targets |
| `dispositions` | tuple[`Disposition`,...] | recorded *why* for each divergence (FR-027) |
| `source_path` | Path | provenance (not serialized) |

**Wing**: `name: str`, `source: Path` (wing's source dir, relative to campaign root), `rooms: tuple[Room,...]`, `trust: "authoritative"|"accelerator"|"reference"` (the HOWTO trust level).

**Room**: `name: str`, `description: str`, `keywords: tuple[str,...]`.

**Validation**: wing names sanitized (mempalace's rule: lowercase, separators→`_`); `source` paths exist under the campaign and are non-overlapping in a way that respects sub-scopes-before-root; at least one wing; recipe_version is known.

---

## Disposition *(authority — the recorded "why", FR-027)*

Per-campaign, per-divergence record. Authored by the human, stored in the campaign, **never decided by mneme**.

| Field | Type | Notes |
|---|---|---|
| `divergence` | str | stable key identifying what differs from the recipe (e.g. `scaffold.wing.chronicle.absent`) |
| `kind` | `"deliberate" \| "pending"` | the two recorded reasons |
| `rationale` | str | required when `deliberate`; the "because that's what I decided" text |
| `recorded` | str (ISO date) | when the decision was recorded |

**Derived state, not stored**: a divergence with **no** matching Disposition is reported `undispositioned` ("needs a decision") — computed by `conform.py`, never written into the authority by mneme.

---

## RenderedWingArtifact *(derived — D3, reuses 001 `DerivedConfig`)*

A wing's `mempalace.yaml` or the root `.mempalaceignore`, regenerated from the authority.

| Field | Type | Notes |
|---|---|---|
| `target` | Path | where mempalace reads it (wing dir / campaign root) |
| `source_sha256` | str | hash of `(authority subtree + recipe version)`; stamped in a header |
| `content` | str | rendered body |

**Coherence rule (Principle V)**: `status` recomputes the hash and FAILs any artifact whose stamp no longer matches — the "edited a derived file" or "authority changed without re-render" case.

---

## ConformanceRow / ConformanceReport *(observed — FR-005/008, mirrors `status.Row`)*

Honest per-campaign state. Built by inspecting the silicon, never the authority alone.

**ConformanceRow**: `campaign: str`, `dimension: "index"|"render"|"recipe"`, `observed: str`, `expected: str`, `state: State`, `disposition: Disposition|None`, `note: str`.

**State** enum: `built` · `stale` · `missing_config` · `divergent_deliberate` · `divergent_pending` · `divergent_undispositioned` · `invalid_config`. (FR-005/006/027.)

- `index` dimension ← `mempalace` drift signal (D2): `built` vs `stale`.
- `render` dimension ← render-stamp coherence (D3): clean vs stale-render.
- `recipe` dimension ← authority-vs-recipe diff (D4) paired with its Disposition → one of the `divergent_*` states or conformant.

**ConformanceReport**: `tuple[ConformanceRow,...]` + an exit code (0 iff no row is a genuine FAIL; a `divergent_deliberate` row is **not** a FAIL; `divergent_undispositioned` and `invalid_config` and stale-render **are**).

---

## TargetConfig *(derived/advisory — FR-022, served over MCP)*

What mneme recommends a campaign adopt: the current recipe resolved against the campaign's existing choices, preserving non-conflicting ones. A `CampaignMempalaceConfig`-shaped value plus a `diff` against the campaign's current authority. Advisory until adopted; never written by the act of reading it.

---

## MigrationPlan *(transient — FR-024/025/026)*

Assistant-authored, human-approved, executed in the working copy. **Not** persisted as authority.

| Field | Type | Notes |
|---|---|---|
| `campaign` | str | per-campaign (FR-024) |
| `steps` | tuple[`MigrationStep`,...] | free-form; each is a content-preserving file/index op |
| `approved_by_human` | bool | execution gate — must be true (FR-024) |

**MigrationStep** `op` ∈ `move` · `split` · `rename` · `reindex` · `write_authority` — a closed set of **content-preserving** operations (FR-025); there is deliberately **no** `rewrite_content` op. A step that would alter document bytes is rejected before execution. Post-run, `migrate.py` re-runs conformance (FR-026) to confirm the *actual* result.

---

## Instructions *(served capability — D8, FR-028/029)*

Not a runtime dataclass so much as served content. **ManagementInstructions**: mneme-owned, versioned-with-recipe prose method (the `MEMPALACE_HOWTO.md` content), shipped in `mneme/recipes/instructions/`. **CampaignUsageGuide**: served from the campaign's `MEMPALACE.md` (read in place, intrinsic — never copied into mneme). Both exposed read-only via MCP prompts/resources, loaded on demand.

## WorkingCopy *(transient manager state — D5, IV)*

mneme's private clone of the campaigns repo. Holds **no authority** — discardable and re-cloneable (Brick Test). `path: Path` (under XDG state), `branch: str` (proposal branch), `remote: str`. Writes land here; the active checkout (read-only to mneme) is never touched.

---

## Relationships

```text
Recipe (mneme-owned, versioned)
   │  resolved against
   ▼
CampaignMempalaceConfig  ── renders ──▶  RenderedWingArtifact(s)  ──▶  mempalace mine ──▶ index
   (authority, in campaign)   (stamped)        (derived, in campaign)        (subprocess)
   ├── Wing ─── Room
   └── Disposition (the recorded "why")
        │
        ▼  compared (observed vs recipe + mempalace drift)
   ConformanceReport ── rows ──▶ status output / MCP get_status
   TargetConfig (recipe resolved) ──▶ MCP get_target_config ──▶ assistant ──▶ MigrationPlan ──(human-approved)──▶ migrate.py (in WorkingCopy)
```
