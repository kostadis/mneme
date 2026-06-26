# Contract: `.mneme/mempalace.yaml` — the per-campaign authority

The **single editable source of truth** for one campaign's mempalace (FR-002/016). Lives in the campaign repo, travels with it (Principle III), survives a mneme wipe (Principle IV / FR-011). mneme **reads** it and **renders** the derived wing files from it; mneme never invents its content (FR-020).

## Location

`<campaign_root>/.mneme/mempalace.yaml`. The `.mneme/` directory holds mneme-managed authority for the campaign; the derived `mempalace.yaml` (per wing) and `.mempalaceignore` (root) live where `mempalace` expects them and are **stamped, do-not-edit** renders.

## Schema

```yaml
campaign: out-of-the-abyss          # required; matches the workspace dir name
recipe_version: "1.0.0"             # required; the recipe version this campaign targets/adopted

wings:                               # required; >=1. The campaign's content decision (FR-020).
  - name: narrative                  # sanitized: lowercase, [-, space] -> _
    source: docs/chapters            # dir relative to campaign root; must exist
    trust: authoritative             # authoritative | accelerator | reference
    rooms:
      - name: chapters
        description: Narrative prose chapters from the campaign bible
        keywords: [chapter, session, narrative, story]
      - name: general
        description: Fallback
        keywords: []
  - name: chronicle
    source: docs/distill_extractions
    trust: accelerator
    rooms: [ ... ]
  - name: abyss                      # the <campaign> reference wing
    source: .                        # root wing
    trust: reference
    rooms: [ ... ]

extra_exclusions:                    # optional; merged OVER the recipe baseline_exclusions
  - custom_tracking_scratch/

dispositions:                        # optional; the recorded "why" for divergences (FR-027)
  - divergence: scaffold.wing.chronicle.absent
    kind: deliberate                 # deliberate | pending
    rationale: "No extraction pipeline for this campaign; 2-wing by design."
    recorded: "2026-06-25"
  - divergence: mechanical.exclusions.notes_indexed
    kind: pending
    recorded: "2026-06-25"
```

## Validation (load-time, all problems reported at once — mirrors `hypostasis/config.py`)

1. `campaign` and `recipe_version` present; `recipe_version` is a known recipe.
2. `wings` non-empty; each wing `name` sanitizes cleanly and is unique; each `source` exists under the campaign root.
3. Wing sources respect **sub-scopes-before-root** (a wing whose source is an ancestor of another wing's source must be mined last; the root wing `source: .` is always last) — so the render can set `.mempalaceignore` to prevent double-mining (FR-004).
4. `trust` ∈ {authoritative, accelerator, reference}.
5. Each `disposition.divergence` is a recognized divergence key; `kind: deliberate` **requires** `rationale`; `recorded` is an ISO date.
6. **No second-authority fields** (mirrors `FORBIDDEN_TOP_LEVEL`): the authority MUST NOT contain rendered-output, index-metadata, or mine-timestamp fields — those are derived/observed, never stored here (Principle III/V).

## Derived from this file (never edited by hand)

- `<wing.source>/mempalace.yaml` for each wing — stamped `# mneme-rendered; source-sha256: <hash>; do-not-edit`.
- `<campaign_root>/.mempalaceignore` — recipe `baseline_exclusions` + `extra_exclusions` + every non-root wing source (double-mine guard), stamped.

A derived file whose stamp no longer matches `sha256(authority-subtree + recipe_version)` is flagged by `mneme mp status` / `render --check` (Principle V coherence).
