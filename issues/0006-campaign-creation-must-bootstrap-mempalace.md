# 0006 — campaign creation must produce a mneme-usable mempalace

**Status:** open (filed 2026-06-25)
**Area:** campaign lifecycle · mempalace management · feature 002
**Related:** `specs/002-manage-campaign-mempalaces/` (FR-012 bootstrap, FR-016 single authority, US4),
[[0004-gm-assistant-campaigns-path]], `MEMPALACE_HOWTO.md`, constitution Principle III (intrinsic state)

## The gap

Feature 002 makes `mneme` *manage* per-campaign mempalaces from a single authority that lives in
the campaign (`.mneme/mempalace.yaml`), with the per-wing `mempalace.yaml` + `.mempalaceignore`
rendered (stamped) from it. But that authority only exists for campaigns that have been
**bootstrapped** (`mneme mp bootstrap`, FR-012) or **migrated** (FR-017). A campaign created by
any other path is born *without* a mneme-usable mempalace, so `mneme mp status` reports it
`missing_config` and it silently falls outside management — exactly the "inconsistent by accident"
problem 002 exists to kill, reintroduced at creation time.

## What we want

**When a campaign is created, it MUST be created with a mempalace that `mneme` can use** — i.e.
the creation path produces (or invokes `mneme mp bootstrap` to produce) a valid
`.mneme/mempalace.yaml` authority from the current recipe scaffold, so the new campaign is
manageable, refreshable, and conformance-checkable from birth with no manual setup step.

Concretely, the campaign-creation flow should:

1. Write a starter `.mneme/mempalace.yaml` from the current recipe scaffold (the FR-012 bootstrap
   payload), choosing the scaffold pattern (3-/2-/1-wing) appropriate to what the campaign has.
2. Render the derived wing `mempalace.yaml` + `.mempalaceignore` (stamped) from that authority.
3. Leave the result conformant to the current recipe (so `mneme mp status` is green or an
   explicit, dispositioned divergence — never `missing_config`).

## Open questions

- **Who owns campaign creation?** There is no `create-campaign` command today (`mneme up` resolves
  an *existing* dir). If `hypostasis`/`mneme` gains one, it calls the bootstrap path directly; if
  campaigns keep being created by hand / by CampaignGenerator, the contract is "run
  `mneme mp bootstrap <campaign>` as the last creation step" (and document it).
- **Writes vs. the active checkout.** Creation legitimately writes into the new campaign's working
  tree (it is being created), so the FR-018 "never touch the active checkout" rule does not apply
  to the create-time bootstrap — but a *later* re-bootstrap/migration still must (private working
  copy). Keep the two paths distinct.
- **Recipe version stamp.** A freshly created campaign should record the current
  `recipe_version`, so it starts life conformant rather than immediately "upgrade available."

## Why it matters (doctrine)

Principle III — a campaign's mempalace config is its intrinsic state; it should exist the moment
the campaign does, not be bolted on later. Closing this makes "every campaign is manageable by
mneme" an invariant established at creation, not a cleanup task.
