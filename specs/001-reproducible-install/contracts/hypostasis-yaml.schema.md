# Contract — `hypostasis.yaml` schema (the single authority)

Authoritative config/wiring entity. Hand-edited. One per deployment. See
[data-model.md](../data-model.md) for field rules; this is the shape + a worked example.

```yaml
venv: ~/.venvs/main                      # required
installer: pip                           # optional: pip | uv (default pip) — package/venv tool

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
  rpg_lib:                               # also external — hypostasis has no start/stop for it yet
    url: http://localhost:8000
    port: 8000
    managed: false
    health: { type: http, path: / }
# NOTE: no turbovecdb service here — turbovecdb is mneme-private storage used EMBEDDED
# (mempalace connects to it directly, not over HTTP); the :8077 HTTP layer belongs to a
# different consumer entirely and was dropped from scope (see tasks.md T020).

components:                              # what hypostasis installs (rpg-lib is external — see services above)
  dgxlib:           { source: { path: ~/src/dgx },               pin: <git-sha-or-tag>,
                      config_template: dgxlib.models.yaml.j2,     config_target: ~/src/dgx/models.yaml }
  turbovecdb:       { source: { pypi: turbovecdb },              pin: <ver> }
  mempalace:        { source: { pypi: mempalace },               pin: 3.3.5,
                      config_template: mempalace.yaml.j2,         config_target: ~/.config/mempalace/mempalace.yaml }
  CampaignGenerator:{ source: { path: ~/src/CampaignGenerator }, pin: <git-sha>,
                      config_template: campaigngenerator.wiring.yaml.j2,
                      config_target: ~/src/CampaignGenerator/config/wiring.yaml }
# NOTE: gm-assistant is NOT a component — it's markdown content shipped with the campaigns
# workspace, not pip-installable (see tasks.md T021).

order:
  install: [dgxlib, turbovecdb, mempalace, CampaignGenerator]
  startup: [dgx, rpg_lib]                # both external — health-checked, gated first, never started
```

*This is the illustrative shape (field names + invariants); `hypostasis.example.yaml` at the
repo root is the current worked reference if the two ever drift.*

## Invariants (validated before any side effect)
1. `pin` is an exact version or git ref — **no ranges, no editable installs**.
2. Every `order.install` name ∈ `components`; every `order.startup` name ∈ `services`.
3. `order.*` are acyclic.
4. Each `managed: true` service defines `start` and `stop`.
5. Each component with a `config_template` defines a `config_target`.
6. No field introduces a second writable authority (no `lockfile`, no write-back target).
7. `installer`, if present, is `pip` or `uv` (default `pip`) — a declared, deterministic choice, not a second store.

## What is deliberately NOT here
- **No installed-version field** — observed live by `status`, never stored (Principle I/V).
- **No lockfile pointer** — pins are already exact in this one file (Principle V).
- **No data-plane contents** — only `data_roots` *locations* are referenced.

## Amended by feature 005 (multi-root + identity)
See `specs/005-multi-root-campaigns/contracts/hypostasis-additions.schema.md` for the full delta.
- A `data_roots` value MAY be **one-or-more paths**: a scalar (1 tree, backward compatible) or a
  list. `data_roots.campaigns` may name several trees; single-valued keys must contain exactly one.
  Each element must be absolute; declared `campaigns` trees must not overlap/nest.
- A top-level **`mneme:`** block (optional) carries the logical fleet identity — `id` (generated
  uuid4, host-independent, authoritative for ownership) and optional `label`. Minted lazily and
  appended to the file if absent; if the block is present, `id` must be non-empty. Not a second
  authority — it is identity belonging to the config entity.
