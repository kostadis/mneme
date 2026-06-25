# 0005 — mneme depends on an underlying "hypostasis" layer that provisions the DGX and rpg-lib

**Status:** open (2026-06-24)
**Area:** architecture · layering · external services · D2
**Related:** `mneme.yaml` (`machines.dgx`, `services.dgx`/`services.rpg_lib` with `managed: false`),
[[0003-query-rpg-lib-direct-access]], constitution Principle I (Silicon Truth), D2 (DGX external)

## The layer

mneme owns the **integration / config plane** for the components it installs and the one service
it renders (CampaignGenerator). But several things mneme depends on are **external** — it
health-checks and interacts with them, but does **not** start or own them:

- the **DGX** model endpoint (`machines.dgx`, vLLM/OpenAI-compatible at `:8001`)
- the **rpg-lib** index service (`library_server` at `:8000`)

Something has to actually **stand these up** — serve the model on the DGX, run `library_server`,
and provide the runtime substrate (process env, GPU, ports, the physical box). That provisioning
layer is **hypostasis** (ὑπόστασις — "that which stands beneath"): the substrate mneme rests on.

```
        mneme            ← integration / config plane (installs components, renders wiring,
          │                 health-checks externals, honest status)
          ▼  depends on
      hypostasis         ← provisions the substrate: DGX model serving, rpg-lib index service,
                            runtime env, ports, the physical hardware
```

## Responsibilities (hypostasis, not mneme)

- Bring up the **DGX endpoint** — spin up vLLM with the served model that `machines.dgx` names;
  keep it reachable at the configured endpoint.
- Run the **rpg-lib index service** (`library_server`) so mneme's consumers (CG's `rpg_retriever`,
  and #0003's eventual HTTP `query_rpg_lib`) can reach it.
- Own the **runtime environment** for these services (the env-delivery wrinkle: mneme starts almost
  no managed services, so process env like `MEMPALACE_BACKEND` / `RPG_LIBRARY_ROOT` is really a
  substrate concern — see the `env:` note in `mneme.yaml`).

## Why this matters / the boundary

- It explains the `managed: false` services in `mneme.yaml`: those are **hypostasis's outputs**,
  not mneme's to start. mneme's job is to interact honestly and report when they're down
  (Principle I — never assume up).
- It keeps mneme's scope clean: mneme does **not** grow SSH/remote-process management or hardware
  provisioning (D2's rationale). That belongs to hypostasis.
- Future: hypostasis could become its own spec/repo (the layer that turns a bare box + the DGX into
  a running substrate), with mneme declaring its dependency on it.

## Not actionable in mneme yet

This is a layering/architecture note, not a mneme code change. It names the dependency so the
`managed: false` externals have an owner, and so the env-delivery question has a home.
