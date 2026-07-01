# Contract: discovery, resolution & lifecycle commands

How mneme finds campaigns across trees and the CLI surface for the claim/provision
lifecycle. Behavioral contract — exact flags are an implementation detail of `tasks.md`.

## Discovery (read-only)

- **Roots**: `campaigns_roots(entity)` returns every declared `campaigns` tree, each
  validated as an existing directory.
- **Enumeration**: every immediate subdirectory of every tree is a campaign (the existing
  per-tree rule, applied to each tree). Result is sorted by `(name, tree)` — deterministic
  and stable across runs (FR-010).
- **No writes, no network** (FR-014, SC-005): discovery reads the on-disk checkout only and
  classifies ownership by reading `owner.yaml`. It never drives git and never writes to a
  campaign.

## Name resolution `find(entity, name)`

| Situation | Result |
|---|---|
| exactly one non-foreign campaign named `name` | that `CampaignRef` |
| >1 non-foreign campaign named `name` (across trees) | **ambiguity error** naming the campaign and every tree it is in (FR-005); no side effect |
| 0 campaigns named `name` | **not-found error** listing the trees searched (FR-006) |
| a foreign-owned copy also exists | excluded from the match set; surfaced separately, not counted as ambiguity (FR-005, US3-4) |

## `mneme integrate <campaign>` (NEW)

Claim a campaign for this mneme — the explicit step before provisioning.

1. Resolve `<campaign>` (name across trees, or an explicit `--dir` path).
2. Classify ownership:
   - `FOREIGN` → **refuse**, reporting the foreign owner's `id` (FR-015). Exit non-zero.
   - `OWNED` → no-op (idempotent), report already-integrated.
   - `UNINTEGRATED` → `ensure_mneme_identity` (mint if first time), then `write_owner`.
3. Writes **only** `.mneme/owner.yaml` — no wings, store, or rendered faces (SC-007).

## `mneme up <campaign>` (EXTENDED)

Provision a campaign. Same resolve + classify as integrate, then:

- `FOREIGN` → **refuse** (FR-017), identical to integrate's refusal.
- `UNINTEGRATED` → integrate first (claim), then run the existing bring-up.
- `OWNED` → run the existing bring-up unchanged (003 behavior).

`up` is a superset of `integrate`: `integrate ⊂ up`.

## `status` (EXTENDED, read-only)

For every discovered campaign, report its membership state alongside existing fields:

- `OWNED` — managed by this mneme.
- `FOREIGN` — owned by another mneme (shows the foreign `id`); needs an operator decision
  (the to-do — Principle IX). Never managed, never re-stamped.
- `UNINTEGRATED` — discovered but not claimed; hint to run `mneme integrate`.
- `UNVERIFIABLE` — this runtime has no identity yet; hint that the first `integrate` mints it.

Status performs no writes and no git network access (FR-014, SC-005/006).

## Per-tree operations (FR-009)

Operations bound to a single tree's git origin act per declared tree:
- proposal/to-do listing iterates each tree, degrading independently (a tree with no origin
  contributes nothing — existing GH #14 behavior, now per-tree).
- publish targets the specific campaign's `tree` origin (no single global root assumption).
