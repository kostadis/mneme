# Contract: .mneme/owner.yaml (campaign membership record)

A campaign's self-declaration of which mneme owns it (Principle III, Intrinsic State). It is
**separate** from `.mneme/mempalace.yaml` (the indexing authority) so it can exist at the
*integrated* stage, before bring-up. It is authoritative for **ownership only**.

## Format

```yaml
# <campaign>/.mneme/owner.yaml
schema_version: "1.0.0"
mneme:
  id: 9f1c7e2a-...-uuid4    # the owning mneme's id — the ONLY field used for classification
  label: kostadis-main      # informational snapshot of the owner's label at claim time
integrated_at: "2026-06-27T18:22:05Z"   # informational ISO-8601; not used for decisions
```

## Invariants

- **No host coordinate.** No machine name, IP, port, hostname, or filesystem path appears in
  this file (Principle II; FR-013/019; SC-009). Ownership is logical and host-independent, so
  the campaign can be brought up by any runtime carrying `mneme.id`.
- **Single owner authority per campaign.** Exactly one `owner.yaml`; its sole writers are
  `mneme integrate` and `mneme up` (one write path — Principle V).
- `schema_version` and `mneme.id` MUST be present and non-empty when the file exists.

## Classification (read-only)

Given this runtime's identity, a campaign is classified:

| Condition | State |
|---|---|
| no `owner.yaml` | `UNINTEGRATED` |
| `owner.yaml.mneme.id == this runtime's id` | `OWNED` |
| `owner.yaml.mneme.id != this runtime's id` | `FOREIGN` |
| this runtime has no identity yet | `UNVERIFIABLE` (status only; mint via `integrate`) |

Matching is on `id` only — `label` may drift and is never used for identity.

## Write rules

- `write_owner` creates `.mneme/owner.yaml` (and `.mneme/` if missing) with this runtime's
  `id`/`label` and a fresh `integrated_at`. It writes **only** this file — no `mempalace.yaml`,
  no rendered faces, no store (SC-007).
- A campaign classified `FOREIGN` MUST NOT be written/re-stamped by any path (FR-015).
- `write_owner` on an `OWNED` campaign is idempotent (may refresh `integrated_at`; `id`
  unchanged).
