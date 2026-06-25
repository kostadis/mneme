# 0005 — hypostasis must provision (not just reference) the DGX + rpg-lib substrate

**Status:** open (filed 2026-06-24; layering clarified 2026-06-25)
**Area:** architecture · layering · external services · D2
**Related:** `hypostasis.yaml` (`machines.dgx`, `services.dgx`/`services.rpg_lib` `managed: false`),
[[0003-query-rpg-lib-direct-access]], constitution Principle I (Silicon Truth), D2 (DGX external)

## Layering (clarified 2026-06-25)

```
  hypostasis            ← configures the ENVIRONMENT (run once): installs the shared libs,
      │                    renders shared config, references + health-checks the DGX/rpg-lib
      ▼ instantiated per campaign by
  mneme up <campaign>   ← runs CampaignGenerator on that prepared environment
```

(The name "hypostasis" — ὑπόστασις, "that which stands beneath" — now belongs to the
environment-config tool. Earlier drafts of this issue used it for the substrate layer, before
the hypostasis/mneme split was clear.)

## The gap

The DGX model endpoint and the rpg-lib index service are **external** (`managed: false`):
hypostasis **references** and **health-checks** them (Principle I — never assume up), but does
**not** yet **start** them. Something has to actually serve the model on the DGX (vLLM) and run
`library_server`.

"Configure the environment" should eventually **include provisioning that substrate** — bringing
up vLLM with the model `machines.dgx` names, and `library_server` for rpg-lib. Today that's
manual / the physical box's job. Making hypostasis own it (SSH / remote process management) is a
materially larger surface, deferred per **D2**.

## Resolved (2026-06-25)

- **env-delivery** — resolved. `mneme up` exports hypostasis's `env:` (`MEMPALACE_BACKEND`, …)
  into CG's process. The `env:` block is the declared requirement; `mneme` delivers it per campaign.
- **who starts CG** — resolved. A per-campaign `mneme` does (`mneme up <campaign>`).

## Still open

- **hypostasis bringing the substrate UP** (not just health-checking it) — provision vLLM on the
  DGX + `library_server` for rpg-lib. A future hypostasis capability (remote/process
  provisioning), deferred per D2.
