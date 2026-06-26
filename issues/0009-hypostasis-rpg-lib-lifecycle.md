# 0009 — hypostasis should start/stop rpg-lib (`library_server`), not just health-check it

**Status:** open (filed 2026-06-26)
**Area:** hypostasis · service lifecycle · substrate
**Related:** [[0005-hypostasis-substrate-layer]] (broad substrate provisioning),
`hypostasis.example.yaml` (`services.rpg_lib` `managed: false`), constitution Principles I & VI,
invariant 4 (managed services declare start/stop)

## The gap

`rpg_lib` is declared `managed: false`: hypostasis **health-checks** `library_server` at
`localhost:8000` but never **starts or stops** it. That's correct for the DGX (remote hardware —
SSH/remote process management is materially harder, deferred per D2 in [[0005-hypostasis-substrate-layer]]),
but `library_server` is a **local process** — its lifecycle is tractable *now* and shouldn't be
lumped with the remote-DGX work.

Today bringing rpg-lib up is manual operational discipline; `mneme up` then gates on it being
reachable (Principle I — never assume) and fails if it isn't. The missing piece is hypostasis
actually owning "bring `library_server` up / take it down".

## What we want

Promote `rpg_lib` to a **managed service** (`managed: true`) with `start` / `stop` (the existing
component model already supports this — invariant 4 requires managed services to declare both):

- a hypostasis-level lifecycle action brings `library_server` up **in dependency order**, then
  health-gates it (start ≠ up — confirm it actually answers, Principle I), and takes it down on
  shutdown;
- one unreachable/failed service is one FAIL, not a wedged run (Principle VI).

## Open questions

- **Where do start/stop live?** A `start`/`stop` script in the rpg-lib repo (mirroring how
  CampaignGenerator exposes `start`/`stop` that `mneme up` already shells out to), referenced from
  `hypostasis.yaml`.
- **Environment-level vs per-campaign.** rpg-lib is a *shared* index service — it should be started
  **once for the environment**, not per campaign. That implies a hypostasis substrate-lifecycle
  command (`hypostasis up`/`down` for managed substrate), which doesn't exist yet — today `mneme up`
  only gates external deps, it doesn't start them. This is the concrete, local-first slice of
  [[0005-hypostasis-substrate-layer]]; the remote-DGX half stays deferred.
- **Ordering vs the DGX.** rpg-lib may itself depend on the DGX endpoint (claudelib); keep the
  declared startup order acyclic (leaf deps first), as the component model already requires.

## Why it matters

Closing this removes a standing piece of "works through operational discipline" — the exact thing
this repo exists to replace with a configured, reproducible, honestly-reported system.
