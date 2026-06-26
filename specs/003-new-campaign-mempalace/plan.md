# Implementation Plan: Mempalace Bring-Up for a New Campaign

**Branch**: `003-new-campaign-mempalace` | **Date**: 2026-06-26 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification + verified ground truth ([research-current-state.md](./research-current-state.md))

## Summary

Give `mneme mp` a **bring-up** verb that takes a *new* campaign (documents, no mempalace) to
configured + provisioned + indexed + backed-up + observable, in one explicit operation — greenfield
(the existing fleet is migrated separately, GH #24).

The spine is the feature-002 pattern extended: **one in-campaign authority → render every face that
names the store → provision the dedicated turbovec store → first-mine → back up the bindings.** The
authority (`.mneme/mempalace.yaml`) gains a **store pointer**; bring-up renders the four derived faces
that today are hand-wired and inconsistent (the fragmentation bug #21/#23):

1. the campaign's `mempalace.yaml` `palace:` + `wing:`/`rooms:` — so the **CLI resolves by directory**
   (walk-up) to this campaign's store (FR-016);
2. the campaign's `config.yaml` `mempalace:` section (CampaignGenerator search);
3. the campaign's entry in the global `~/.mempalace/config.json` `palaces:` alias map (merged, never
   clobbering other campaigns);
4. a **per-campaign mempalace MCP registration** (a `.mcp.json` server) pointed at this campaign's
   store — never a hardcoded path (FR-017; the anti-pattern behind CG #112).

Store reality (verified, turbovec — **not** chroma): a store is `~/.mempalace/palaces/<campaign>/`
with `turbovec/<collection>/store.sqlite3` (the **bindings = source of truth**) + a rebuildable
`index.tvim` cache + `knowledge_graph.sqlite3`. So:

- **Provision** = declare the store in the authority, render the alias + `palace:` faces, and let the
  first `mempalace mine` create it.
- **Back up = preserve the bindings**: copy the `store.sqlite3` files + `knowledge_graph.sqlite3`;
  **exclude** the rebuildable `index.tvim` and the dead-legacy `chroma.sqlite3`.
- **Restore = copy the bindings back**; turbovecdb rebuilds `index.tvim` from `store.sqlite3`
  (generation-stamped, **no re-embed**) and auto-prunes entries whose source is gone. **Re-generation
  (re-embed) is a separate explicit verb**, never automatic.
- **`mneme up` gates**: it brings up the campaign *runtime* and **fails** if the campaign's store is
  not brought up / unhealthy — it never brings the store up itself (FR-010/014).
- **Observable**: the new campaign appears in `mneme mp status` (built/conformant, never
  `missing_config`); bring-up reports each step's observed outcome and any owed follow-up (Principle IX).

## Technical Context

**Language/Version**: Python 3.11+ (extends the existing `mneme/mempalace/` package from feature 002).

**Primary Dependencies**: reuse 002 — `PyYAML`, the `hypostasis.render` stamp helpers (jinja2),
`typer`. `mempalace` is invoked **only by subprocess** (`init`, `mine`, `status`, `search`, all with
`--palace`), resolved from `~/.venvs/main/bin/mempalace`. Backup/restore are **filesystem copies** of
the turbovec `store.sqlite3` files (stdlib `shutil`). The per-campaign MCP face is a rendered
`.mcp.json`. No new runtime dependency; no import of `mempalace`/`turbovecdb` internals.

**Storage**:
- *Authority* — `.mneme/mempalace.yaml` in the campaign, extended with a **store pointer**.
- *Derived faces* — campaign `mempalace.yaml` (`palace:`/wings), campaign `config.yaml` `mempalace:`,
  the global `~/.mempalace/config.json` `palaces:` entry (merged), and the per-campaign `.mcp.json` —
  all rendered/stamped from the authority, never hand-edited.
- *Store* — `~/.mempalace/palaces/<campaign>/` (turbovec), owned by mempalace; the bindings
  (`store.sqlite3`) are the backup target.
- *Bindings backup* — under a configured backups location (XDG state / a `data_roots.backups`),
  labeled derived/disposable.

**Testing**: `pytest`. Extend the 002 **stub `mempalace`** to honor `--palace`, create a fake store
dir on `mine`, and answer `status`. Unit: store-pointer authority load/validate, the four-face
render (golden files; config.json **merge** not clobber), backup selects `store.sqlite3`/excludes
`index.tvim`+`chroma.sqlite3`, restore-preserves-bindings, the up-gate. Integration: end-to-end
bring-up over a temp campaigns root + fake palaces; directory-context CLI resolution; the per-campaign
MCP face points at the right palace; Brick Test (delete store → re-bringup reproduces).

**Target Platform**: Linux/WSL2; real campaigns under `~/campaigns/`; embeddings/LLM at the local
substrate endpoints (must be reachable for a real `mine` — relates to substrate bring-up #1).

**Project Type**: single project — extends the `mneme/mempalace/` package + the `mneme mp` CLI group;
adds an `mneme up` store-health gate. No new top-level component.

**Performance Goals**: not a hot path. The first `mine` is bounded by the embedding endpoint; backup
is a file copy. No throughput targets.

**Constraints**: **greenfield** (no brownfield logic — #24 owns that); turbovec backend only; render,
never hardcode (the MCP face must resolve via the campaign's pointer); single authority (store pointer
in the authority, faces rendered + coherent); restore preserves bindings (no auto re-embed); `mneme
up` gates and fails; per-campaign isolation.

### Decisions ratified for this plan (detail in [research.md](./research.md))

1. **Authority owns the store pointer; four faces rendered from it** (FR-015) — incl. a **merge** into
   the shared global `config.json` (never clobber other campaigns' entries).
2. **Provision = declare + render + first-mine** (the store is created by `mempalace mine`; mneme
   does not format a store itself) — lowest coupling (Principle VIII).
3. **Backup = copy `turbovec/*/store.sqlite3` + `knowledge_graph.sqlite3`**, exclude `index.tvim`
   (rebuildable) and `chroma.sqlite3` (dead). **Restore = copy back; turbovecdb rebuilds the index +
   auto-prunes; re-embed is a separate explicit verb.**
4. **Per-campaign MCP face** = a rendered `.mcp.json` `mempalace` stdio server with the campaign's
   palace injected (env/arg), never a hardcoded path.
5. **`mneme up` store-health gate** = an observed check (store present + turbovec health) that fails
   the runtime start if the mempalace isn't brought up — reusing the existing substrate-gate shape.
6. **Subprocess to `mempalace` only**; backup/restore are filesystem ops on the store dir.

## Constitution Check (v1.1.0 — Principles I–IX)

*GATE: must pass before Phase 0. Re-checked after Phase 1.*

| Principle | Gate | This plan |
|---|---|---|
| I — Silicon Truth | observed, never declared | ✅ bring-up reports each step's *observed* result; `mneme up` gates on an observed store-health check; status reads the store, not the authority's claim. |
| II — Sovereign Identity / no Infra Proxy | no hardcoded coordinates | ✅ store path/alias come from the authority/config; the MCP face is **rendered** with the campaign's pointer — directly kills the hardcoded-`~/.mempalace/palace` anti-pattern (CG #112). |
| III — Intrinsic State | state travels with the entity | ✅ the authority **and the store pointer** live in the campaign; the global `config.json` entry is a *render* of it, not a separate truth. |
| IV — Transient Viewer / Brick Test | reconstruct from the entity | ✅ the index is derivable (SC-007: delete store → re-bringup reproduces); backups are derived/disposable; mneme owns nothing irreplaceable. |
| V — One Authority / no stale copies | single source, coherent renders | ✅ the in-campaign authority is the sole source; all four faces are rendered + coherence-checked (incl. the global registry, **merged**). Within the store, turbovec's `store.sqlite3`=truth / `index.tvim`=derived mirrors this. |
| VI — Federated Authority | per-entity, degrade independently | ✅ bring-up/backup operate per-campaign; one failure is isolated; `config.json` render merges (one campaign never wedges another). |
| VII — Logical Datasets / low coupling | render, don't import | ✅ render into mempalace's native faces; `mempalace` is subprocess-only; no `turbovecdb` import. |
| VIII — Transform the Constraint | simpler coordinate first | ✅ reuse mempalace's palace-resolution + **turbovecdb's auto-prune & generation stamp** instead of building a freshness/rebuild subsystem (the preserve-bindings decision); let `mine` create the store instead of formatting one. |
| **IX — Observability** | state + to-do discoverable | ✅ the new campaign is immediately in `mneme mp status` (never `missing_config`); bring-up reports steps + owed follow-up; backup state and "right store everywhere" (SC-008) are surfaced, not remembered. |

**Anti-patterns checked:** Optimistic Lies (gates/status read the store — avoided); Infrastructure
Proxy (MCP/path rendered, not hardcoded — avoided, fixes CG#112 pattern); Fragmented State (four faces
from one authority — avoided, fixes #21/#23); Split-Brain (the global registry is a render, not a
second authority); **Opacity / Tribal State** (new campaign + backup state visible — avoided).

**One design care, not a violation:** the global `~/.mempalace/config.json` is a **shared** file every
campaign's render touches — rendering MUST **merge** this campaign's entry and never clobber others
(see Complexity Tracking). No unjustified violations → **GATE PASS**.

## Project Structure

### Documentation (this feature)

```text
specs/003-new-campaign-mempalace/
├── spec.md
├── research-current-state.md   # the verified ground truth (input)
├── plan.md                     # this file
├── research.md                 # Phase 0 — the ratified decisions
├── data-model.md               # Phase 1 — store pointer, faces, bindings backup, bring-up report
├── quickstart.md               # Phase 1 — validation scenarios (SC-001..008)
├── contracts/
│   ├── cli.md                          # mneme mp bringup/backup/restore/regenerate + the up-gate
│   ├── authority-store.schema.md       # the store-pointer authority extension + the 4 render faces
│   ├── backup.md                       # bindings backup/restore/regenerate (turbovec store.sqlite3)
│   └── mcp-registration.md             # the per-campaign .mcp.json mempalace server face
├── checklists/requirements.md
└── tasks.md                    # Phase 2 (/speckit-tasks — NOT here)
```

### Source Code (repository root)

```text
mneme/mempalace/            # existing 002 package — extended
├── authority.py            # + store-pointer field (alias + path) on the authority
├── render.py               # + the 4 derived faces (mempalace.yaml palace:, config.yaml mempalace:,
│                           #   config.json palaces[ MERGE ], .mcp.json); all stamped
├── provision.py            # NEW — declare + render the store pointer; first-mine to create the store
├── backup.py               # NEW — bindings backup/restore (copy turbovec store.sqlite3) + regenerate (explicit re-mine)
├── bringup.py              # NEW — orchestrate: bootstrap authority → render faces → provision → first-mine → backup → report
├── health.py               # NEW — observed store-health (present + turbovec store/index consistency) for the up-gate + status
├── runner.py               # + init / mine --palace / status --palace / search wrappers
└── cli.py                  # + `mp bringup|backup|restore|regenerate`
mneme/lifecycle.py          # + store-health gate in `up()` (fail if the campaign mempalace isn't brought up)

tests/
├── unit/                   # store-pointer authority, 4-face render (config.json merge), backup selection, restore-preserves, up-gate
└── integration/            # end-to-end bringup; directory-context CLI; MCP face → right palace; Brick Test

# Campaign data written at CREATE time directly into the campaign workspace (FR-005); the global
# config.json render merges; the bindings backup lands under the configured backups location.
```

**Structure Decision**: extend `mneme/mempalace/` (the 002 manager). Bring-up is per-campaign
management built on 002's authority/render/refresh; it is **not** a new component. Store provisioning
here is lightweight (declare + first-mine) — the heavier hypostasis substrate/service work (#1/#12/#20)
is separate and the eventual migration (#24) reuses this machinery.

## Complexity Tracking

| Choice | Why needed | Simpler alternative rejected because |
|---|---|---|
| **Rendering into the shared global `~/.mempalace/config.json`** (a file outside the campaign) | mempalace resolves palaces partly via this global alias map; for resolution to work the campaign's alias must exist there | It is still a **render** of the in-campaign authority (not a second authority — V). The care: the file is **shared**, so the render must **merge** this campaign's entry and re-stamp, never overwrite the whole file (a clobber would wedge other campaigns — VI). Alias only in-campaign was rejected: mempalace's global resolution wouldn't see it. |
| **Backup = filesystem copy of `store.sqlite3`** (not a mempalace command) | mempalace has no native backup/restore; the bindings live in turbovec's `store.sqlite3`, a plain copyable SQLite file | "Use mempalace export" rejected — export is markdown-only with no reimport (verified). Copying the source-of-truth file + letting turbovecdb rebuild the index on open is the lowest-coupling way to preserve bindings (VIII). |
| **Let `mempalace mine` create the store** rather than mneme provisioning it | the store is created on first mine; mneme only needs to *point* mempalace at the per-campaign path | mneme formatting/initializing a turbovec store itself would import/duplicate turbovecdb internals (couples to a churning backend) — rejected (VII/VIII). |
