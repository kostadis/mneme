# Validation harness — SC-005 reproducibility acid test

**This is a proof environment, NOT a deployment target for 001.** It exists to *prove* the
SC-005 claim — "one `mneme.yaml` reproduces the system on a fresh environment with no manual
edits" — in true isolation. A clean container has no pre-existing `~/.venvs/main`, no `~/src`
checkouts, and none of the host's operator discipline, so a passing run here can't be a
configured-box illusion (see [research D10](../research.md#d10--containerized-validation-harness-sc-005-acid-test)).

> Containerizing the six components *as the deployment model* is a different, larger feature
> (a future `002`). Do not let this harness grow into that by momentum.

## What it does
`docker compose run --rm mneme-validate` runs, inside a clean container, the full loop:
`mneme install → mneme up → mneme status → change-value → mneme apply → status`
against a `mneme.yaml` whose component sources are pinned git refs (fetched at build), so the
container is reproducible from the one authority alone.

## DGX endpoint — pick one (deliberate sub-decision, test both ways)
Per research D2 the DGX is an *external* dependency `mneme` health-checks, not starts.
- `DGX_MODE=real` — container reaches the real `192.0.2.10:8001`; exercises the real
  external-dependency path. Point `mneme.yaml` at a different IP to also prove SC-004.
- `DGX_MODE=stub` — a stub endpoint stands in; assert `mneme status` reports the *real* DGX
  **unreachable honestly** (exit 1, FAIL) — no False Green Dashboard (Principle I).

## Status
Skeletons below encode intent. The runnable Dockerfile/compose are completed in
`/speckit.implement` (they depend on the `mneme` CLI, which 001 builds). Marked here so the
plan's reproducibility claim has a concrete, named home rather than living as a promise.
