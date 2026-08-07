# Phase 1 Data Model — Portable vs Host-Local Campaign State

Entities, the portable/host-local classification that is this feature's thesis, and the
validation rules and state transitions derived from the requirements.

---

## The classification

Every value mneme writes or reads falls into exactly one column. This table is the feature.

| value | where it lives | portable? | why |
|---|---|---|---|
| `campaign`, `recipe_version`, `wings`, `dispositions`, `extra_exclusions` | `.mneme/mempalace.yaml` (tracked) | **portable** | describes the campaign's content, true on any host |
| `store.alias` | `.mneme/mempalace.yaml` (tracked) | **portable** | names the palace; the name is host-independent |
| ~~`store.path`~~ | *removed from tracked state* | — | was `$HOME`-dependent — the bug |
| `mneme.id` in `owner.yaml` | `.mneme/owner.yaml` (tracked) | **portable** | a logical fleet id (005 FR-019) — now actually reachable from a second host |
| `mneme.id` in `hypostasis.yaml` | host config | **host-local file, fleet-wide value** | the same value is *copied* to each host in the fleet; it is not derived per host |
| `data_roots.mempalace` | host config | **host-local** | where this machine keeps palaces |
| `data_roots.campaigns` | host config | **host-local** | where this machine checked the trees out (005) |
| resolved palace path | nowhere — computed | **derived** | `<mempalace_root>/palaces/<alias>` |

The axis 005 used was *derived vs authority*, which splits files. This axis splits **fields**,
and it cuts through `.mneme/mempalace.yaml`.

---

## Entities

### StorePointer *(changed)*

`mneme/mempalace/models.py:83-89`

| field | type | source | notes |
|---|---|---|---|
| `alias` | `str` | tracked authority | normalized by `_normalize_wing_name`; defaults to the campaign name |
| `path` | `Path` | **derived at load** | `mempalace_root / "palaces" / alias`. In-memory only — never serialized (FR-010) |

Invariants:

- `to_yaml` emits `{"alias": ...}` and nothing else. The absence of a serializer for `path` is
  what enforces SC-005 — it is not enforceable by convention.
- `path` is stable per `(host, alias)` — two campaigns with the same alias produce the same
  path, which is why FR-016 must refuse them.
- `path` may be a symlink; mneme follows it transparently (FR-011a).

### CampaignMempalaceConfig *(unchanged shape)*

`models.py:92-105`. Only its `store` member's semantics change. 002-era authorities with no
`store` block continue to load as `store=None`, gated by `require_store` at bring-up
(`authority.py:181-187`) exactly as today.

### Store root *(new)*

Not a dataclass — a resolved value.

```
config.mempalace_root(entity) -> Path
    entity.data_roots["mempalace"]  via single_root()   # declared
    ~/.mempalace                                        # default (FR-012)
```

Validation is inherited: `data_roots` values must be absolute (`config.py:280-285`), and
`single_root` rejects a key declared with more than one path (`config.py:76-77`).

### MnemeIdentity *(unchanged shape, new lifecycle)*

`hypostasis/models.py:58`. The dataclass does not change. What changes is how a host comes to
have one — see the state machine below.

### Owner evidence *(new, transient)*

```
ownership.owner_ids(campaign_dirs) -> dict[str, list[str]]   # id -> campaign names
```

Read-only, built on `read_owner`. Never persisted — it is computed to make one decision and
discarded. It is *not* a registry (Principle III/IV): the campaigns remain the only record.

---

## State machines

### Host identity state

```
                    ┌──────────────────────────────────────┐
                    │  NONE  (no mneme: block in config)   │
                    └───┬──────────┬───────────────────┬───┘
      evidence: 0 ids   │          │  evidence: 1 id   │  evidence: >1 id
                        ▼          ▼                   ▼
                    ┌───────┐   ┌──────────────┐   ┌──────────────┐
                    │ MINT  │   │ REFUSE       │   │ REFUSE       │
                    │ (auto)│   │ name the id, │   │ list all ids │
                    └───┬───┘   │ offer adopt  │   │ + campaigns  │
                        │       └──────┬───────┘   └──────┬───────┘
                        │              │ operator          │ operator
                        │              ▼                   ▼
                        │        `identity adopt <id>`  `identity adopt <id>`
                        │              │                   │  or `identity mint`
                        ▼              ▼                   ▼
                    ┌──────────────────────────────────────────┐
                    │            ESTABLISHED                   │
                    │  (mneme.id present in hypostasis.yaml)   │
                    └──────────────────────────────────────────┘
                                       │
                       `identity adopt <other>` → refused if the
                       current id owns campaigns, unless --force (FR-007)
```

Transitions never write to a campaign (FR-008). Adoption is never automatic (FR-005).

### Campaign membership *(unchanged states, changed enforcement point)*

`OwnerState` keeps its four values (`ownership.py:26-30`): `UNINTEGRATED`, `OWNED`, `FOREIGN`,
`UNVERIFIABLE`. What changes:

- classification moves **out of** `discover.find()` into the command layer, so it applies to
  `--dir`-named campaigns too (FR-018, research R6);
- `UNVERIFIABLE` now means "identity not established" and its message names the adopt-or-mint
  choice rather than minting alone (FR-009).

### Authority load outcomes *(new)*

```
read .mneme/mempalace.yaml
   │
   ├── no store block            → store=None       (002-era; require_store gates bring-up)
   ├── store.alias only          → derive path      → OK
   ├── store.alias + legacy path
   │      ├── resolves equal     → derive path      → OK + status to-do row  (FR-013)
   │      └── resolves different → AuthorityError naming both paths          (FR-014)
   └── invalid                   → AuthorityError (existing all-problems-at-once behavior)
```

Symlinks are resolved on both sides before the equal/different comparison.

---

## Validation rules

| rule | source | enforced in |
|---|---|---|
| A serialized authority contains no store path | FR-010, SC-005 | `authority.to_yaml` |
| Palace location = root + `"palaces"` + alias, and nothing else | FR-011, FR-011a | `authority._parse` |
| A legacy path equal to the derived one loads and is reported | FR-013 | `authority.validate` + `conform` |
| A legacy path different from the derived one fails every operation | FR-014 | `authority.validate` |
| One unloadable campaign does not wedge fleet status | FR-014a | `conform._campaign_rows` (existing `AuthorityError` catch at `:165-168`) |
| Two campaigns may not share a store alias | FR-016 | discovery-level check, both routes |
| Ownership is enforced however the campaign was named | FR-018 | command layer, not `find()` |
| Identity is never adopted automatically | FR-005 | `cli._ensure_identity` resolver |
| Adoption refuses to orphan campaigns owned by the current id | FR-007 | `identity adopt` |
| Identity operations write no campaign | FR-008 | `adopt_mneme_identity` touches only the config |

---

## Migration

Two campaigns carry a legacy `store.path` today. Both resolve to `<derived>` on the host whose
`$HOME` they name and conflict on the other:

| campaign | tracked path | this host (`kroussos`) | other host (`kostadis`) |
|---|---|---|---|
| `toee` | `/home/kroussos/.mempalace/palaces/toee` | equal → to-do | **different → fatal** |
| `obelisk` | `/home/kostadis/.mempalace/palaces/obelisk` | **different → fatal** | equal → to-do |

Migration is deleting one line from each file in the `~/campaigns` repo. No re-mine, no
re-render: `~/.mempalace/palaces/{toee,obelisk}` is exactly what both hosts derive. No
migration command is built — a two-line edit does not justify machinery (Principle VIII), and
`mp status` surfaces the owed work (Principle IX).
