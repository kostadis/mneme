# Quickstart & Validation: Manage Campaign Mempalaces

Runnable scenarios that prove the feature works end-to-end and map to the spec's Success Criteria. Implementation details live in `tasks.md`; this is the validation guide.

## Prerequisites

- `pip install -e '.[dev]'` in `~/src/mneme` (provides `mneme`).
- `mempalace` installed at its pin (hypostasis installs it); `mneme` invokes it by subprocess.
- A `hypostasis.yaml` with `data_roots.campaigns` pointing at the active campaigns checkout.
- Fixtures mirroring the real spread: `full` (3 wings + ignore + MEMPALACE.md, like out-of-the-abyss), `ignore-only` (like Phandalin), `bare` ×3 (like Hillsfar/Obelisk/toee). Integration tests use a **stub `mempalace`** binary on `PATH` and a **temp git repo** as the campaigns remote.

---

## Scenario A — Honest cross-campaign status (US2 → SC-001, SC-007, SC-012)

```bash
mneme mp status
```

**Expect**: one block per campaign. `full` → `built` (or `stale` if docs changed); `ignore-only`/`bare` → `missing_config — skipped`. Any recipe divergence shows its disposition (`deliberate: <rationale>` / `pending`) or `undispositioned — needs a decision`. Hand-edit a derived wing `mempalace.yaml` → status flags **stale-render** (Principle V). Independent check: an inspection of each campaign on disk agrees with the report (SC-007).

---

## Scenario B — Refresh from each campaign's own authority (US1 → SC-002)

```bash
mneme mp refresh --all --dry-run     # preview per-wing mine order, sub-scopes before root
mneme mp refresh out-of-the-abyss    # real: render derived files, then mempalace mine per wing
```

**Expect**: dry-run prints the wing order (e.g. `distill_extractions → chapters → <root>`); `bare` campaigns reported skipped; an `invalid_config` campaign FAILs alone while others proceed (SC-006). Re-running changes nothing (idempotent — FR-014). The index reflects the campaign's own wings/exclusions.

---

## Scenario C — Single authority, coherent renders (US-foundation → SC-008)

```bash
mneme mp render out-of-the-abyss --check   # coherence check only
# edit .mneme/mempalace.yaml (add a room), then:
mneme mp render out-of-the-abyss           # regenerate stamped wing yaml + .mempalaceignore
mneme mp status out-of-the-abyss           # render rows clean again
```

**Expect**: editing the **authority** and re-rendering leaves no derived file out of sync; editing a **derived** file directly is caught as stale-render. Exactly one place to edit (SC-008).

---

## Scenario D — Publish an upgrade without touching active checkouts (US3 → SC-003, SC-009)

```bash
git -C "$CAMPAIGNS_CHECKOUT" status --porcelain > /tmp/before
mneme mp publish --recipe 2.0.0 --dry-run    # per-campaign preview; writes nothing
mneme mp publish --recipe 2.0.0              # commit to private working copy; push proposal branch
git -C "$CAMPAIGNS_CHECKOUT" status --porcelain > /tmp/after
diff /tmp/before /tmp/after                  # MUST be empty (SC-009)
```

**Expect**: the proposal branch `mneme/recipe-2.0.0` exists on the remote; the **active checkout is byte-unchanged** (SC-009); no campaign's canonical config changed (that needs adoption). A change that would clobber a deliberate choice is surfaced as a conflict, not applied (SC-004).

---

## Scenario E — Per-campaign manual adoption (US3 → SC-003)

```bash
mneme mp status                       # one campaign shows "upgrade available, not yet adopted"
mneme mp adopt out-of-the-abyss       # campaign-side gate (non-migration upgrade), in working copy
# owner merges/pulls the proposal branch into the active checkout
mneme mp status out-of-the-abyss      # now conformant; others still "upgrade available"
```

**Expect**: adoption is per-campaign and opt-in; non-adopted campaigns remain a legitimate `divergent_pending` state, not a failure (FR-021).

---

## Scenario F — Assistant-guided migration, verbatim & verified (US5 → SC-010, SC-011)

```bash
mneme mp mcp &                        # advisory server
# In an assistant session connected to the server:
#   get_target_config("oversized-bible-campaign")  -> recommended structure
#   get_campaign_inventory(...)                    -> 8200-line bible, no chapters wing
#   (assistant reasons out a plan: split bible -> docs/chapters, add narrative wing)
#   human reviews & approves  ->  plan.json (approved_by_human: true)
mneme mp migrate oversized-bible-campaign --plan plan.json --dry-run
mneme mp migrate oversized-bible-campaign --plan plan.json
```

**Expect**: `get_target_config` returns a recommendation without the human hand-assembling it (SC-011). Execution moves/splits files but every retained document is **byte-for-byte unchanged** (SC-010) — a plan with a content-rewriting step is refused (FR-025). After apply, mneme verifies the **actual** index conforms (FR-026); an incomplete migration is reported as such, never as healthy.

---

## Scenario G — Brick Test (manager is transient → SC-005)

```bash
pip uninstall mneme && pip install -e .   # wipe + reinstall the manager
mneme mp status                            # same view; zero re-entry of per-campaign settings
```

**Expect**: every campaign's authority + dispositions survive (they live in the campaign); the recipe is package code; the working copy is re-cloneable. Management reconstructs entirely from the campaigns (SC-005 / Principle IV).

---

## Success-criteria coverage

| SC | Scenario |
|---|---|
| SC-001 cross-campaign true state | A |
| SC-002 one-command refresh | B |
| SC-003 publish-once / adopt-per-campaign | D, E |
| SC-004 choices preserved, conflicts surfaced | D |
| SC-005 Brick Test, no state in mneme | G |
| SC-006 missing/invalid never aborts run | A, B |
| SC-007 reported == on disk | A |
| SC-008 one place to edit | C |
| SC-009 active checkout never modified | D |
| SC-010 verbatim migration | F |
| SC-011 programmatic recommendation | F |
| SC-012 every divergence has a recorded why | A |
