# Contract: hypostasis.yaml additions (mempalace root + identity provenance)

Delta against `specs/005-multi-root-campaigns/contracts/hypostasis-additions.schema.md`.
`hypostasis.yaml` remains the **single editable authority** (Principle V); these changes
introduce no second writable store — they move one value *into* this authority that was
wrongly living in a campaign.

## `data_roots.mempalace` — where this host keeps its palaces (NEW)

```yaml
data_roots:
  campaigns:
    - ~/campaigns
  backups: ~/.mneme/backups
  mempalace: ~/.mempalace        # NEW, OPTIONAL — defaults to ~/.mempalace when absent
```

**Rules**:

- **Single-valued.** Like `backups`, it is read through `single_root()`; declaring more than
  one path is a config error.
- MUST resolve to an absolute path after `~`/env expansion (existing per-element rule).
- **OPTIONAL with a default of `~/.mempalace`**, so no existing configuration requires an edit
  (FR-012). Every host that has never thought about this key keeps working unchanged.
- It is a **host coordinate** (Principle II): it names where *this machine* stores palaces and
  is injected into resolution. It is deliberately not derivable from, and never written into,
  any campaign.

**What consumes it**:

| consumer | derived value |
|---|---|
| a campaign's palace location | `<mempalace_root>/palaces/<store.alias>` |
| the global alias registry mneme merges into | `<mempalace_root>/config.json` |

Both were previously hardcoded to `~/.mempalace` in component logic — `bringup.py:27`,
`bringup.py:31`, `bootstrap.py:35`, `conform.py:117` — which is the Infrastructure Proxy this
key retires.

## `mneme` — identity provenance clarified (CHANGED)

The block's **shape is unchanged** from 005:

```yaml
mneme:
  id: 64cf8b36-e823-4b8e-8353-d08fe707f9be   # generated; the logical fleet identity
  label: kostadis-main                        # OPTIONAL, informational
```

What changes is **how a host comes to have one**. 005's rule read:

> If absent, mneme **mints** it once on the first claim … it generates a `uuid4` and appends
> the `mneme:` block.

That rule silently forks the fleet on a second host. It is replaced by:

- If absent and the declared trees contain **no** ownership records → mint, as before.
- If absent and the declared trees name **exactly one** owner → **do not mint.** Refuse, name
  that id and the campaigns carrying it, and offer `mneme identity adopt <id>` or
  `mneme identity mint` (FR-002).
- If absent and the trees name **more than one** owner → refuse and list them (FR-004).
- mneme MUST NOT adopt an identity automatically under any circumstance (FR-005).

**A fleet identity is expected to appear identically on more than one host.** 005 FR-019
already specified this ("MAY be present on more than one hypostasis runtime / physical
machine"); this contract makes it operational. The supported way to put it on a second host is
`mneme identity adopt <id>` — or, since the file is hand-authored, copying the block. Both are
first-class; the command exists so the remedy is discoverable (Principle IX), not because
hand-editing is wrong.

**Write discipline** (unchanged from 005, extended to adoption): appending or replacing the
`mneme:` block is a targeted textual edit. Existing content and comments are never rewritten.

## Documentation requirement

`hypostasis.example.yaml`'s commented `mneme:` block currently reads "Minted automatically on
the first `mneme integrate`/`up` if absent." That sentence is now wrong in the multi-host case
and MUST be corrected to state that a second host **adopts** the fleet's existing id rather
than minting its own.

## Unchanged

`data_roots` scalar-or-list normalization, the non-overlapping-campaigns-trees rule,
absolute-path validation, all-at-once validation with exit code 2, and the
`FORBIDDEN_TOP_LEVEL` set.
