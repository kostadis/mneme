# Research: Manage Campaign Mempalaces (Phase 0)

The spec already resolved the major scope/architecture forks (recipe scope, recipe home, single authority, manual adoption gate, free-form migration). This file records the **technical** decisions needed to implement them, each as Decision / Rationale / Alternatives.

---

## D1 — How mneme invokes mempalace

**Decision**: Subprocess to the `mempalace` CLI only (`mempalace mine`, `status`, `sync`, `split`), resolved from the configured venv exactly as `mneme/lifecycle.py` resolves CampaignGenerator's `start`. mneme never imports `mempalace.*`.

**Rationale**: Principle VII/VIII — `mempalace` is a sovereign component hypostasis already installs at a pin; it stays ignorant of mneme. A subprocess seam is the lowest-coupling integration and matches the existing lifecycle pattern. `mempalace`'s internals (`palace.py`, `miner.py`) are large and version-churning (v3.3.5); importing them would couple mneme to private APIs.

**Alternatives**: (a) import `mempalace` as a library — rejected: couples mneme to internal APIs, makes mneme non-transient. (b) reimplement mining — rejected: duplicates the component this feature exists to *orchestrate*, not replace.

---

## D2 — Staleness signal (built / stale)

**Decision**: Derive staleness from `mempalace` itself — `mempalace sync --dry-run` / `mempalace status` reveal source-vs-index drift. mneme stores **no** index metadata (no mine timestamps, no doc hashes) of its own.

**Rationale**: Principle III/IV — any mneme-side record of "what was indexed when" is a horcrux that must be hand-synced and would break the Brick Test. The index's truth lives with the index; mneme asks `mempalace`. Principle I — "stale" is then an *observed* fact, not a cached claim.

**Alternatives**: mneme records a content hash of each wing's source set at mine time — rejected: second store of the index's truth (III), and drift-prone. **Open implementation detail** (not blocking): the exact `mempalace` subcommand/flag that yields a clean machine-readable drift list; `sync --dry-run` is the candidate, confirmed at implementation against the installed pin.

---

## D3 — The per-campaign authority and its derived renders

**Decision**: One authority file per campaign, `.mneme/mempalace.yaml`, **in the campaign repo**. It declares the campaign's wings (each: source dir, rooms[name/description/keywords]), campaign-specific exclusions, the targeted recipe version, and the **dispositions** list. The per-wing `mempalace.yaml` files and the root `.mempalaceignore` are **rendered** from it and **stamped** with a SHA-256 of `(authority subtree + recipe version)` using the existing `hypostasis/render.py` mechanism. A one-time consolidation (`bootstrap`/`migrate`) folds today's scattered files into the authority (FR-017).

**Rationale**: Principle V — exactly the single-authority/derived-render shape 001 already proved; reusing the stamp gives free coherence + drift detection (`status` flags a hand-edited wing yaml whose stamp no longer matches). Keeping the authority under `.mneme/` separates "edit here" from `mempalace`'s own consumed files cleanly and avoids the `mempalace init`-overwrites-`mempalace.yaml` hazard (the hazard hits the *derived* file, which mneme regenerates anyway).

**Alternatives**: (a) treat the existing scattered wing yamls as the authority — rejected by the spec (FR-016). (b) store authority outside the campaign (in mneme) — rejected: violates "config lives in the campaign" (II/III).

---

## D4 — The mneme-owned recipe

**Decision**: A versioned YAML in the package, `mneme/recipes/mempalace.recipe.v1.yaml`, with two sections: **mechanical** (enforced) — baseline `.mempalaceignore` entries (`summaries/`, `logs/`, `voice/`, `examples/`, `notes/`, tooling files, `.claude/`, `MEMPALACE.md`), the "mine sub-scopes before root" ordering rule, and tunnel room-naming (shared `npcs`/`world` across wings); and **scaffold** (recommended, overridable) — the 3-wing narrative/chronicle/`<campaign>` pattern with 2-wing and 1-wing fallbacks. Carries a semver used in render stamps and conformance.

**Rationale**: FR-007/FR-015 — recipe owned by mneme, two layers, scaffold overridable. Distilled directly from `MEMPALACE_HOWTO.md` (the prose stays as rationale). Versioning lets `status` say "campaign targets recipe v1; current is v2 → upgrade available."

**Alternatives**: recipe in the campaigns repo next to the prose — rejected by the spec (FR-015). Hardcode conventions in code — rejected: not inspectable/versionable, can't diff "which recipe version."

---

## D5 — Publish / adopt carrier (git)

**Decision**: mneme maintains a **private working copy** (clone) of the campaigns repo under mneme-managed cache state (e.g. `$XDG_STATE_HOME/mneme/campaigns-work`). `publish` renders the upgrade for every campaign there, commits, and pushes a **proposal branch** (e.g. `mneme/recipe-v2`). **Adoption is the campaign owner merging/pulling** that branch into their active checkout — the manual Gate 2 (FR-021). Opening a PR via `gh` is an optional convenience flag, not required.

**Rationale**: Principle VIII — git already *is* a propose/review/adopt mechanism with per-entity granularity; reusing it avoids a bespoke sync daemon or workflow engine. FR-018/SC-009 — writing only in the clone guarantees the active checkout is byte-unchanged. A branch (not direct-to-`main`) gives the second review gate the spec requires without forcing GitHub PR ceremony.

**Alternatives**: direct push to `main` — rejected: no Gate 2. Always-PR — rejected: forces GitHub UI into a possibly-offline local workflow; offered as opt-in instead. mneme edits the active checkout and lets the GM sort it out — rejected outright (FR-018).

---

## D6 — MCP server (framework + tool surface)

**Decision**: A dedicated mneme MCP server using the official **MCP Python SDK (FastMCP)**, exposing **advisory, read-only** tools: `get_target_config(campaign)` (FR-022 — recipe resolved for the campaign, preserving non-conflicting choices), `get_status(campaign?)` (conformance + dispositions), and `get_campaign_inventory(campaign)` (current docs/wings/structure, so the assistant can reason about a migration). All **mutation** (render/publish/adopt/migrate/bootstrap) stays in the `mneme mp` CLI behind preview-then-apply; the MCP server calls no write path.

**Rationale**: FR-022 + US5 — the adoption workflow is conversational and needs these inputs programmatically. Keeping the server read-only keeps it a *viewer*, not a runtime dependency (IV/VI): down server ⇒ GM still works, mutation still possible via CLI. mempalace ships its own separate stdio MCP server (search over the palace) — orthogonal, not a dependency.

**Alternatives**: put mutating tools on the MCP server — rejected: would let an assistant mutate campaign data without the CLI's preview-then-apply gate, and make the server load-bearing. Reuse mempalace's MCP server — rejected: different concern (palace search vs. recipe/conformance/adoption).

---

## D7 — Migration planning trust model (the deliberate deviation)

**Decision**: The migration plan is **reasoned out freely by the assistant** (not a deterministic mneme transform) and is **mandatorily human-approved** before execution (FR-024). mneme supplies inputs (target config via D6, inventory) and enforces three invariants independent of the plan: **verbatim** content (FR-025 — move/split/rename/re-index only, never rewrite), **write-isolation** (FR-018 — execute in the working copy), and **post-migration verification** (FR-026 — confirm the actual resulting index conforms, distinguishing "didn't finish" from "deliberately different").

**Rationale**: Recorded as the single Constitution deviation (see plan Complexity Tracking). The checkpoint the doctrine demands is preserved — it moves from "deterministic generation" to "human approval + mechanical integrity invariants." This is the *good* LLM pattern (LLM drafts → human imposes/approves structure → execution renders inside it), not the bad one (LLM structures → feeds downstream unreviewed).

**Alternatives**: deterministic plan generator — rejected by the user/spec (structure is campaign-specific judgment). Auto-execute the assistant's plan — rejected: removes the human checkpoint on a precision (scope) decision.

---

## D8 — Serving instructions on demand (FR-028/029)

**Decision**: The MCP server (D6) additionally serves the *instructions* for mempalace work as **loadable capabilities** via MCP **prompts** (user-invocable, e.g. `manage-mempalace`) and **resources** (assistant-loadable, e.g. `mneme://campaign/<name>/usage-guide`). **Management instructions** (the `MEMPALACE_HOWTO.md` method) are **mneme-owned**, versioned with the recipe, and ship in the package alongside it. The **per-campaign usage guide** is served **from the campaign's `MEMPALACE.md`** (read in place). Both are read-only and loaded on demand, never always-on context.

**Rationale**: These docs were the human's way of telling the assistant *how* to manage a palace; serving them turns a manual copy-paste step into a discoverable, versioned capability — and **grounds** US5's free-form migration in the shared method (FR-024 reasons freely, but now from the recipe-as-instructions, not improvisation). Ownership follows the lines already drawn: method is cross-campaign → mneme-owned (FR-015/029); usage guide is per-campaign → intrinsic to the campaign (Principle III). Read-only keeps the server a transient viewer (IV). On-demand loading matches mempalace's load-what-you-need token ethos and mempalace's own `instructions` surface (prior art).

**Alternatives**: keep pasting docs by hand — rejected (the whole point of the request; not versioned, not discoverable). Always-inject the instructions into context — rejected: token cost and defeats "load when I need to." Relocate `MEMPALACE.md` into mneme — rejected: it is the campaign's intrinsic content (III).

## Resolved unknowns

All Technical-Context unknowns are resolved above. Two **non-blocking implementation details** to confirm against the installed `mempalace` pin during build (not design risks): the exact `mempalace` subcommand/flags for a machine-readable drift list (D2), and whether `mempalace split` is reused for bible-splitting during migration or that step stays a plan-authored file operation (D7). Neither changes the architecture.
