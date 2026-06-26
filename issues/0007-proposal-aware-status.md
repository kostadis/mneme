# 0007 — `mneme mp status` should surface mneme-created proposal branches (a to-do view)

**Status:** resolved (filed + implemented 2026-06-26) — `proposals.py` + a TODO section on
`mneme mp status` (`--no-proposals` / `--no-fetch`), with unit + real-git integration tests.
**Area:** observability · mempalace management · feature 002
**Related:** `specs/002-manage-campaign-mempalaces/` (FR-005 observed state, FR-021 manual adoption gate,
FR-018 write isolation), [[0008-constitution-observability-gap]], constitution Principle I (Silicon Truth)

## The gap

`mneme mp status` reports the observed state of each campaign's *index/config* (built / stale /
missing / divergent), but it is blind to the **git-level to-do list**: the proposal branches mneme
pushed (`mneme/bootstrap-*`, `mneme/recipe-*`, `mneme/adopt-*`) that the operator has not yet
integrated. Because adoption is a deliberate manual gate (FR-021) and mneme never touches the
active checkout (FR-018), an outstanding proposal is invisible — the operator has to *remember*
that a branch is waiting. That is the "upgrade available, not yet adopted" idea (FR-005/021)
surfaced only inside an already-adopted authority, never at the branch level where the actual
pending work lives.

## What we want

A "what do I need to do" view: `mneme mp status` gains a **TODO** section listing the mneme
proposal branches and their integration state, read-only and honest (it reads the remote, never
asserts). Pending proposals are informational, not failures (non-adoption is legitimate — FR-021),
so they do **not** change the exit code.

```
TODO — proposals awaiting integration:
  mneme/bootstrap-obelisk   pending   touches: obelisk   → git merge origin/mneme/bootstrap-obelisk
  mneme/recipe-2.0.0        pending   touches: all       → review & merge
  mneme/adopt-saga-1.0.0    merged    → safe to delete: git push origin --delete mneme/adopt-saga-1.0.0
```

## Design

- New `mneme/mempalace/proposals.py`, read-only git via an injectable runner (mirrors
  `workcopy.py`):
  - optional `git fetch origin` (default on; `--no-fetch` to stay offline),
  - enumerate `refs/remotes/origin/mneme/*`,
  - **merged?** `git merge-base --is-ancestor <ref> HEAD` (exit 0 → merged → offer the delete),
    else **pending** (offer the merge),
  - **touches:** `git diff --name-only HEAD...<ref>` → top-level dirs → campaign names.
  - No git origin / fetch fails → return `[]` and continue (degrade independently — Principle VI).
- `mneme mp status` prints a TODO section after the per-campaign rows (suppress with
  `--no-proposals`; offline with `--no-fetch`). Exit code stays driven by conformance only.
- No change to the authority model, the recipe, or the write paths.

## Rejecting a proposal (documented behaviour, not new code)

Because the proposal is only a branch (the campaign tree was never touched — FR-018), rejecting it
is trace-free: `git push origin --delete mneme/<branch>` (and `git fetch --prune`). Nothing is
removed from the campaign itself. The TODO line for a *merged* proposal offers the same delete as
cleanup.

## Tasks (tracked in tasks.md Phase 9)

- proposals.py helper + unit/integration tests (real git over a local bare remote)
- TODO section on `mneme mp status` (+ `--no-proposals` / `--no-fetch`)
