# Contract: `mneme mp` command group

New subcommand group on the existing `mneme` CLI. Mirrors the existing exit-code convention: `0` OK, `1` runtime failure, `2` invalid config. All commands take `--config/-c` (the `hypostasis.yaml` that supplies `data_roots.campaigns`). Reads use the **active checkout**; writes use the **private working copy** (never the active checkout).

---

### `mneme mp status [CAMPAIGN] [--config PATH]`  → FR-005/008/013/027 (US2)

Honest cross-campaign conformance. With no `CAMPAIGN`, reports every discovered campaign; otherwise one.

- Reads observed state only: render-stamp coherence + `mempalace` drift (D2) + authority-vs-recipe diff paired with dispositions.
- Output: one block per campaign with rows for `index` / `render` / `recipe`, each showing `state` (see data-model `State`), and for a divergence its disposition (`deliberate: <rationale>` / `pending`) or **`undispositioned — needs a decision`**.
- Shared backing store is not conflated (FR-013): per-campaign wings reported separately.
- **Exit 0** iff no genuine FAIL. `divergent_deliberate` is **not** a FAIL; `divergent_undispositioned`, `invalid_config`, stale-render, and (with `--strict`) `stale` index **are**.
- A `missing_config` campaign is reported and skipped, never a hard failure (FR-006).

---

### `mneme mp refresh [CAMPAIGN | --all] [--dry-run] [--config PATH]`  → FR-003/004/006/014 (US1)

(Re)build each campaign's index from **its own authority**, via `mempalace mine` per wing in **sub-scopes-before-root** order (FR-004). Idempotent (FR-014).

- Renders derived wing artifacts first if stale (calls the same logic as `render`), then mines.
- `--dry-run` previews the per-wing mine plan and order; starts nothing (mirrors `mneme up --dry-run`).
- `missing_config` → skipped with a notice; `invalid_config` → that campaign FAILs alone, others proceed (FR-006).
- Reads/uses the active checkout's documents (observed truth — FR-019). Writes only the index (mempalace's store), never the campaign repo.

---

### `mneme mp render CAMPAIGN [--check] [--config PATH]`  → FR-016 (Principle V)

Regenerate the derived wing `mempalace.yaml` + `.mempalaceignore` from the authority, **stamped**. `--check` verifies coherence without writing (used by `status`). Writes (without `--check`) target the **working copy** when the campaign is repo-backed.

---

### `mneme mp publish [--recipe VERSION] [--dry-run] [--open-pr] [--config PATH]`  → FR-009/010/018 (US3)

Render the recipe upgrade for **every** campaign into the private working copy and push a **proposal branch**. Preview-then-apply (FR-010).

- `--dry-run` (default behavior is preview): lists, per campaign, exactly what would change and what is preserved; writes nothing.
- On apply: commits to the working copy, pushes branch `mneme/recipe-<version>`; `--open-pr` additionally opens a PR via `gh` if available.
- **Never** edits an active checkout (FR-018; verified by SC-009). Preserves each campaign's content choices; a change that would overwrite a deliberate choice is surfaced as a conflict, not applied (FR-009).
- Does **not** change any campaign's canonical config — that is adoption (FR-021).

---

### `mneme mp adopt CAMPAIGN [--config PATH]`  → FR-021 (US3, mechanical case)

The campaign-side manual gate for a **non-migration** upgrade: bring this one campaign's authority to the published recipe, in the working copy, for the owner to merge/pull. For upgrades that need data migration, see the assistant-driven flow (MCP + `migrate`, below). Records the new `recipe_version` in the authority. Per-campaign, opt-in; other campaigns unaffected.

---

### `mneme mp migrate CAMPAIGN --plan PLAN.json [--dry-run] [--config PATH]`  → FR-023/024/025/026 (US5)

Execute a **human-approved** migration plan in the working copy. Plan is produced interactively (assistant via MCP) and must carry `approved_by_human: true` (FR-024).

- Rejects any step outside the content-preserving op set; a step that would alter document bytes is refused (FR-025).
- `--dry-run` shows the file/index operations; applies nothing.
- After apply: re-runs conformance and reports whether the **actual** resulting index conforms, distinguishing incomplete/failed from deliberately-different (FR-026). Safe to resume/re-run (idempotent; interrupted migration never reported healthy).

---

### `mneme mp bootstrap CAMPAIGN [--config PATH]`  → FR-012/017 (US4)

Write a starter `.mneme/mempalace.yaml` (from the current recipe scaffold) into a campaign that has none, **in the working copy**, for the owner to customize and adopt. Also the consolidation entry point for FR-017 (scatter → single authority). Preview-then-apply.

---

### `mneme mp mcp [--config PATH]`  → FR-022 (US5)

Run the advisory MCP server (see `mcp-tools.md`). Read-only; no mutation.
