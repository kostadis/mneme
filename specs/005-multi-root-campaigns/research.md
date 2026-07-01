# Research: Multi-Root Campaign Discovery & Membership (Phase 0)

Resolves the concrete bindings the spec deliberately left open. The behavioral decisions
(list-of-trees, observe-not-drive, ambiguity-errors, generated identity, explicit
integrate, report-only boot, one-logical-mneme-many-runtimes) were settled with the
operator during specify/clarify; this file binds them to code shapes.

---

## R1 — `data_roots` value shape: uniform tuple

**Decision**: `ConfigEntity.data_roots: dict[str, tuple[Path, ...]]`. Every value is a
tuple; a scalar in YAML normalizes to a 1-tuple, a list to an N-tuple. `campaigns` is the
only key that uses >1 today, but the type is uniform to avoid special-casing.

**Rationale**: Backward compatibility is automatic (scalar → 1-tuple → identical behavior,
FR-002). A uniform type keeps `config.py` validation a single loop. Per-element absolute
checks reuse the existing loop at `config.py:234`.

**Consequences for single-valued keys** (`backups`, `fivetools`): add
`single_root(entity, key) -> Path` that returns the sole element and raises if a key
expected to be single has >1. `backup.py:33` switches from `data_roots.get("backups")`
to `single_root(entity, "backups")`. `render.py:47` emits each value as a list of strings.
Test fixtures (`tests/fixtures/__init__.py`, `tests/unit/test_*`) that pass a bare `Path`
get updated to pass a 1-tuple, or `make_entity` normalizes for them.

**Alternatives rejected**: (a) keep `dict[str, Path]` and add a separate `campaign_roots`
field — special-cases campaigns, two code paths. (b) `Path | list[Path]` union values —
every reader must branch on type; worse than uniform tuple.

---

## R2 — Discovery & resolution over many trees

**Decision**:
- `campaigns_root()` → `campaigns_roots(entity) -> tuple[Path, ...]` (validates each exists).
- `discover(entity)` iterates every tree, applies the current immediate-subdir rule per
  tree, returns a flat `list[CampaignRef]` sorted by `(name, tree)` for determinism (FR-010).
- `CampaignRef` gains `tree: Path` (which declared tree it came from) and
  `owner_state: OwnerState` (OWNED / FOREIGN / UNINTEGRATED).
- `find(entity, name)` collects all refs whose `name == name`. Excludes FOREIGN from the
  match set (surfaced separately). If >1 non-foreign match → `DiscoveryError` ambiguity,
  naming the campaign and every tree (FR-005). 0 matches → not-found error listing trees
  searched (FR-006). Exactly 1 → that ref.

**Overlap/nesting validation**: `campaigns_roots()` (or config validate) rejects declared
trees where one is a prefix of another (after resolve), so a campaign is never discovered
twice (FR-004, edge case).

**Rationale**: Keeps the existing per-tree rule and `_existing_wing_dirs` untouched; the
generalization is "loop over trees." `CampaignRef.path` is unchanged, so the many
downstream `ref.path` consumers (mcp/server.py, refresh, conform, bringup, backup) keep
working without edits beyond what membership adds.

---

## R3 — mneme identity: shape, storage, and one-time mint

**Decision**: New top-level block in `hypostasis.yaml`:

```yaml
mneme:
  id: 9f1c...-uuid4      # generated, stable, host-independent
  label: kostadis-main   # optional, human-readable, informational
```

Modeled as `MnemeIdentity(id: str, label: str | None)` on `ConfigEntity` (field
`mneme_identity: MnemeIdentity | None`). Parsed in `config.py:_parse`; `validate()`
requires `id` to be present-and-nonempty *if* the block exists (absence is allowed —
it triggers mint).

**Mint**: `ensure_mneme_identity(config_path) -> MnemeIdentity` — loads the file; if no
`mneme.id`, generate `uuid.uuid4()` and **append** a `mneme:` block to the file via a
targeted text insertion (not a full `yaml.safe_dump` rewrite), preserving the operator's
existing content/comments/order. Idempotent thereafter. Invoked lazily by the first
operation that needs to stamp (`integrate`, and `up` when it auto-integrates). Reports the
minted id/label to the operator (Observability).

**Rationale**: Identity belongs in the one config authority (FR-011/012, Principle V), and
must be host-independent (FR-019, Principle II). Textual append respects "human owns
`hypostasis.yaml`" (constitution Authority & Human Checkpoint) — we never clobber their
file. `uuid4` is collision-free without coordination, fitting the federated, input[∞]
assumption (no central allocator).

**Alternatives rejected**: (a) `ruamel.yaml` round-trip to preserve comments on a full
rewrite — adds a dependency for a one-time append; textual append is enough. (b) store
identity in a separate `~/.mneme/identity` file — a second store outside the authority
(Principle V smell). (c) require the operator to hand-author the id — the operator chose
*generated*; a UUID is not a meaningful human decision to make by hand.

**Status with no identity yet**: `status` is read-only and cannot mint. If no identity
exists, status reports "mneme identity not yet minted (run `mneme integrate` to mint)" and
classifies any `owner.yaml`-bearing campaign as *unverifiable* rather than guessing.

---

## R4 — `.mneme/owner.yaml`: format & classification

**Decision**: A small standalone file, separate from `mempalace.yaml` (so it exists at the
*integrated* stage, before bring-up):

```yaml
# .mneme/owner.yaml
schema_version: "1.0.0"
mneme:
  id: 9f1c...-uuid4      # AUTHORITATIVE for ownership; matched against this runtime's id
  label: kostadis-main   # informational snapshot of the owner's label at claim time
integrated_at: "2026-06-27T18:22:05Z"   # informational
```

No host/machine/path field (FR-013/019, SC-009). **Classification** `classify(campaign_dir,
identity) -> OwnerState`:
- no `owner.yaml` → `UNINTEGRATED`
- `owner.yaml.mneme.id == identity.id` → `OWNED`
- else → `FOREIGN`

Match is on `id` only; `label` is never used for identity (it can drift).

**Rationale**: One owner authority per campaign, intrinsic to it (III), reconstructable
(IV/FR-018). `schema_version` lets the record evolve (mirrors `recipe_version` on the
existing authority). `integrated_at` is the only timestamp and is informational, so the
file is reproducible enough for tests (timestamp asserted by presence/format, not value).

---

## R5 — `integrate` vs `up`, and foreign-owned refusal

**Decision**:
- `mneme integrate <campaign>` — resolve the campaign (R2), `classify`; if FOREIGN → refuse
  with the foreign owner's id (FR-015); if OWNED → no-op (idempotent); if UNINTEGRATED →
  `ensure_mneme_identity` then `write_owner` (only `.mneme/owner.yaml`, nothing else,
  SC-007). New command in `mneme/cli.py` beside `up`.
- `mneme up <campaign>` — same resolve+classify; FOREIGN → refuse; UNINTEGRATED → integrate
  first (claim) then run the existing bring-up; OWNED → bring-up as today (FR-017).
- Boot/sync and `status` — never call `write_owner`; only `classify` + report (FR-014).

**Rationale**: `integrate ⊂ up` matches "a variant of `up` that just drops the file." The
single writer of `owner.yaml` is these two explicit commands, so there is exactly one
write path (Principle V coherence). Foreign refusal is the concrete no-split-brain rule.

---

## R6 — Per-tree operations (proposals, publish)

**Decision**: Operations that read a tree's git origin act **per tree**:
- `publish._clone_workcopy` (`publish.py:70`) currently calls `campaigns_root()` for one
  origin. It becomes per-tree: publish targets a specific campaign → use that campaign's
  `ref.tree` origin. (If a publish spans the whole fleet, iterate trees.)
- `cli.py:94` proposals listing iterates each tree, concatenating to-do lines, degrading
  per-tree (a tree with no origin contributes nothing, as today — GH #14 behavior).

**Rationale**: FR-009 — no single global tree. Per-tree keeps the federated property (VI):
one tree without an origin doesn't fail the others.

---

## R7 — Testing strategy

**Decision**: Reuse pytest + fixtures. New/updated coverage:
- unit: scalar config still parses to 1-tuple and behaves identically (FR-002/SC-002);
  list parses to N-tuple; validate rejects a relative element and overlapping trees;
  `discover` enumerates across two trees deterministically; `find` raises on ambiguous and
  not-found; `classify` returns OWNED/FOREIGN/UNINTEGRATED; `ensure_mneme_identity` mints
  once and is idempotent and appends (existing content preserved).
- integration: `status` lists campaigns from two trees with membership state and writes
  nothing (assert mtimes unchanged); `integrate` creates only `owner.yaml`; `up`
  auto-integrates then provisions; foreign-owned `owner.yaml` causes integrate/up to refuse
  and status to flag it.

**Rationale**: Mirrors the existing test layout; SC-002/005/006/007/009 each map to a test.
