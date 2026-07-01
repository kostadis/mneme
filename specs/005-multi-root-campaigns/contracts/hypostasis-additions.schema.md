# Contract: hypostasis.yaml additions (data_roots list + mneme identity)

Delta against `specs/001-reproducible-install/contracts/hypostasis-yaml.schema.md`. The
`hypostasis.yaml` remains the **single editable authority** (Principle V); these additions
introduce no second writable store.

## `data_roots` — now one-or-more paths per key

```yaml
data_roots:
  # NEW: list form — one parent directory holding several independent trees
  campaigns:
    - ~/src/campaigns-monorepo     # tree A (e.g. one GitHub remote, possibly sparse)
    - ~/src/toee                   # tree B (different remote) → campaign at ~/src/toee/toee
  # STILL VALID: scalar form (backward compatible) — behaves as a single-tree fleet
  backups: ~/.mneme/backups
  fivetools: ~/src/5etools-kostadis/data
```

**Rules**:
- A value MAY be a scalar string (1 tree) or a list of strings (N trees). Scalars normalize
  to a 1-element list; existing configs are unchanged (FR-002).
- Every element MUST resolve to an absolute path after `~`/env expansion (existing rule,
  now per-element).
- The `campaigns` trees MUST NOT overlap or nest (no element a path-prefix of another), so a
  campaign is never discovered twice (FR-004).
- Keys consumed as single-valued (`backups`, `fivetools`) MUST contain exactly one element;
  more than one is a config error.
- All-at-once validation: every violation is reported together before any side effect (exit
  code 2), consistent with the existing loader.

## `mneme` — the logical fleet identity (NEW)

```yaml
mneme:
  id: 9f1c7e2a-...-uuid4    # generated; AUTHORITATIVE owner identity; host-independent
  label: kostadis-main      # OPTIONAL human-readable name (informational)
```

**Rules**:
- The block is OPTIONAL in a hand-authored file. If absent, mneme **mints** it once on the
  first claim (`integrate`, or `up` when it auto-integrates): it generates a `uuid4` and
  **appends** the `mneme:` block to `hypostasis.yaml` without rewriting existing content,
  then reports the minted identity (FR-012, research R3).
- If present, `id` MUST be non-empty.
- `id` MUST NOT encode a host, IP, port, or path (Principle II; FR-019). It is a logical
  identity that MAY be configured identically on more than one runtime/machine.
- `label` is never used for ownership decisions — only `id` is.

## Forbidden-field check (unchanged)

The existing `FORBIDDEN_TOP_LEVEL` set (lockfile, installed_versions, …) is unchanged; the
`mneme:` block is not a second authority — it is identity that belongs to the config entity.
