# Contract — `hypostasis.yaml` schema (the single authority)

Authoritative config/wiring entity. Hand-edited. One per deployment. See
[data-model.md](../data-model.md) for field rules; this is the shape + a worked example.

```yaml
venv: ~/.venvs/main                      # required

machines:                                # required (>=1; must include dgx)
  dgx:
    endpoint: http://192.0.2.10:8001/v1
    default_model: Qwen/Qwen3-Next-80B-A3B-Instruct-FP8

data_roots:                              # referenced only — data-plane out of scope
  fivetools: ~/src/5etools-kostadis/data
  campaigns: ~/campaigns

services:
  dgx:                                   # external dependency — checked, not started
    url: http://192.0.2.10:8001/v1
    managed: false
    health: { type: http, path: /v1/models }
  turbovecdb:
    url: http://127.0.0.1:8077
    port: 8077
    managed: true
    health: { type: http, path: /health }
    start: "turbovecdb-service --port 8077"
    stop:  "pkill -f turbovecdb-service"
  rpg_lib:
    url: http://localhost:8000
    port: 8000
    managed: true
    start: "python -m rpg_lib.server"
    stop:  "pkill -f rpg_lib.server"

components:                              # the six in-scope units (FR-011)
  dgxlib:           { source: { path: ~/src/dgx },               pin: <git-sha-or-tag>,
                      config_template: dgxlib.models.yaml.j2,     config_target: ~/src/dgx/models.yaml }
  turbovecdb:       { source: { pypi: turbovecdb },              pin: <ver> }
  mempalace:        { source: { pypi: mempalace },               pin: 3.3.5,
                      config_template: mempalace.yaml.j2,         config_target: ~/.config/mempalace/mempalace.yaml }
  rpg_lib:          { source: { path: ~/src/mytools/rpg-lib },   pin: <git-sha> }
  CampaignGenerator:{ source: { path: ~/src/CampaignGenerator }, pin: <git-sha>,
                      config_template: campaigngenerator.config.yaml.j2,
                      config_target: ~/src/CampaignGenerator/config/config.yaml }
  gm_assistant:     { source: { path: ~/campaigns/gm-assistant }, pin: <git-sha> }

order:
  install: [dgxlib, turbovecdb, mempalace, rpg_lib, CampaignGenerator, gm_assistant]
  startup: [dgx, turbovecdb, rpg_lib]    # dgx (external) gated first; managed ones started in order
```

## Invariants (validated before any side effect)
1. `pin` is an exact version or git ref — **no ranges, no editable installs**.
2. Every `order.install` name ∈ `components`; every `order.startup` name ∈ `services`.
3. `order.*` are acyclic.
4. Each `managed: true` service defines `start` and `stop`.
5. Each component with a `config_template` defines a `config_target`.
6. No field introduces a second writable authority (no `lockfile`, no write-back target).

## What is deliberately NOT here
- **No installed-version field** — observed live by `status`, never stored (Principle I/V).
- **No lockfile pointer** — pins are already exact in this one file (Principle V).
- **No data-plane contents** — only `data_roots` *locations* are referenced.
