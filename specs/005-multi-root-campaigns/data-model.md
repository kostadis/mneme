# Data Model: Multi-Root Campaign Discovery & Membership (Phase 1)

Frozen dataclasses, no I/O in the models themselves. Identity lives in the `hypostasis`
config authority; ownership records live in each campaign. See [research.md](./research.md)
for the binding rationale and [contracts/](./contracts/) for the on-disk formats.

---

## Config authority changes (`hypostasis/models.py`, `hypostasis/config.py`)

### `data_roots` — value type change

`ConfigEntity.data_roots: dict[str, tuple[Path, ...]]` (was `dict[str, Path]`).

| Aspect | Rule |
|---|---|
| Scalar in YAML | normalized to a 1-tuple (backward compatible — FR-002) |
| List in YAML | normalized to an N-tuple |
| Validation | every element absolute after `~`/env expansion; declared `campaigns` trees non-overlapping (no element a path-prefix of another) — FR-004 |
| Single-valued keys | `single_root(entity, key)` returns the sole element, errors if >1 (used by `backups`, `fivetools`) |

### `MnemeIdentity` *(new — the logical fleet identity, FR-012/019)*

New dataclass; new optional field `ConfigEntity.mneme_identity: MnemeIdentity | None`.

| Field | Type | Notes |
|---|---|---|
| `id` | str | generated `uuid4`; AUTHORITATIVE for ownership; host-independent |
| `label` | str \| None | optional human-readable name; informational only |

**Validation**: if the `mneme:` block is present, `id` MUST be non-empty. Absence is legal
and triggers a one-time lazy mint (`ensure_mneme_identity`, research R3). `id` MUST NOT
encode a host/path.

---

## Ownership (`mneme/mempalace/ownership.py` — new module)

### `OwnerState` *(enum)*

`UNINTEGRATED` (no `owner.yaml`) · `OWNED` (id matches this runtime) · `FOREIGN` (id is a
different mneme). `UNVERIFIABLE` is reported by status when this runtime has no identity yet
(can't classify without one — R3).

### `Owner` *(the parsed `.mneme/owner.yaml`)*

| Field | Type | Notes |
|---|---|---|
| `schema_version` | str | record format version (e.g. `1.0.0`) |
| `mneme_id` | str | the owning mneme's `id` — the only field used for classification |
| `label` | str \| None | informational snapshot of the owner label at claim time |
| `integrated_at` | str \| None | ISO-8601 timestamp; informational |

**No host/machine/path field** (FR-013/019, SC-009). Functions (pure-ish; I/O isolated):
- `read_owner(campaign_dir) -> Owner | None`
- `classify(campaign_dir, identity) -> OwnerState`
- `write_owner(campaign_dir, identity) -> Owner` — writes `.mneme/owner.yaml` only;
  callers are exactly `integrate` and `up` (R5).

---

## Discovery (`mneme/mempalace/discover.py`)

### `CampaignRef` *(extended)*

| Field | Type | Notes |
|---|---|---|
| `name` | str | campaign dir name (unchanged) |
| `path` | Path | campaign dir (unchanged — keeps all downstream consumers working) |
| `tree` | Path | **new** — the declared tree this campaign was found under |
| `has_authority` | bool | `.mneme/mempalace.yaml` present (unchanged) |
| `wing_dirs` | tuple[Path, ...] | minable wings (unchanged) |
| `owner_state` | OwnerState | **new** — OWNED / FOREIGN / UNINTEGRATED (/ UNVERIFIABLE) |

### Functions

| Function | Change |
|---|---|
| `campaigns_roots(entity) -> tuple[Path, ...]` | renamed from `campaigns_root`; returns all declared trees; validates each is an existing dir |
| `discover(entity) -> list[CampaignRef]` | iterate every tree × immediate subdirs; classify ownership; sort by `(name, tree)` for determinism (FR-010) |
| `find(entity, name) -> CampaignRef` | search all trees; exclude FOREIGN from the match set; >1 non-foreign → ambiguity error naming every tree (FR-005); 0 → not-found listing trees (FR-006) |

---

## Campaign lifecycle (state transitions)

```text
        discover (read-only)            mneme integrate            mneme up
  ┌───────────────────────────┐   ┌──────────────────────┐   ┌──────────────────┐
  │  in a declared tree, no    │   │ owner.yaml written    │   │ wings/store/index │
  │  owner.yaml                │──▶│ (this mneme's id)     │──▶│ rendered (003)    │
  │  state: UNINTEGRATED       │   │ state: OWNED          │   │ has_authority=true│
  └───────────────────────────┘   └──────────────────────┘   └──────────────────┘
                │                            ▲
                │ owner.yaml names another    │ up auto-integrates if UNINTEGRATED
                ▼ mneme                       │
        state: FOREIGN ── refused by integrate/up; surfaced by status (never re-stamped)
```

- `discover`/`status` cause **no** transition (read-only — FR-014).
- `integrate`: UNINTEGRATED → OWNED (writes `owner.yaml`); OWNED → OWNED (idempotent);
  FOREIGN → refuse (FR-015/016).
- `up`: UNINTEGRATED → OWNED → provisioned; OWNED → provisioned; FOREIGN → refuse (FR-017).
- Moving a campaign between trees preserves `owner.yaml`, so ownership is unchanged (US4-6).

---

## Relationships

- One `ConfigEntity` ⇒ many trees (`data_roots["campaigns"]`) ⇒ many `CampaignRef`.
- One `MnemeIdentity` (this runtime) classifies every `CampaignRef` against its campaign's
  `Owner`. The same `MnemeIdentity.id` may exist on multiple runtimes/machines (FR-019).
- `Owner.mneme_id` is the cross-reference to a `MnemeIdentity.id`; equality = OWNED.
