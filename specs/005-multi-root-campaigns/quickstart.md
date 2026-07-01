# Quickstart: validating Multi-Root Campaign Discovery & Membership

End-to-end validation that the feature works. Maps each step to the success criteria
(SC-00x) in [spec.md](./spec.md). Assumes the `005-multi-root-campaigns` branch checked out
and the package installed in the dev venv. Implementation lives in `tasks.md`.

## Prerequisites

- Two campaign trees on disk, e.g.:
  - `~/src/campaigns-monorepo/` with `oota/`, `phandalin/`
  - `~/src/toee/` with `toee/`
- `hypostasis.yaml` declaring both trees:
  ```yaml
  data_roots:
    campaigns:
      - ~/src/campaigns-monorepo
      - ~/src/toee
  ```
  (No `mneme:` block yet — the first `integrate` will mint it.)

## Scenario 1 — discover across two trees, read-only (SC-001, SC-005)

```bash
mneme mp status
```

**Expect**: `oota`, `phandalin`, and `toee` all listed (deterministic order), each with its
path and a membership state of `UNINTEGRATED` (and `UNVERIFIABLE` identity note, since no
identity is minted yet). Re-run after recording tree mtimes — **no campaign or git tree is
modified**, and the run works offline.

## Scenario 2 — backward compatibility (SC-002)

Temporarily set `data_roots.campaigns` to the single scalar `~/src/campaigns-monorepo`.

```bash
mneme mp status
```

**Expect**: identical output to the pre-feature behavior for those campaigns (scalar → single
tree). Restore the list form afterward.

## Scenario 3 — claim with `mneme integrate` (SC-007, mint via R3)

```bash
mneme integrate toee
mneme mp status
```

**Expect**: `hypostasis.yaml` gains a minted `mneme:` block (uuid + reported to you), and
`~/src/toee/toee/.mneme/owner.yaml` now exists naming that id — **and nothing else** (no
`mempalace.yaml`, no store). `status` now shows `toee` as `OWNED`, others still `UNINTEGRATED`.
Verify `owner.yaml` contains **no host/path** (SC-009).

## Scenario 4 — provision with `mneme up` auto-integrating (FR-017)

```bash
mneme up phandalin
```

**Expect**: `phandalin` is integrated first (gets `owner.yaml`), then brought up (wings,
store, rendered faces per feature 003). `status` shows it `OWNED` with authority present.

## Scenario 5 — foreign-owned is refused and surfaced (SC-006, FR-015)

Hand-edit `~/src/toee/toee/.mneme/owner.yaml`, changing `mneme.id` to a different uuid.

```bash
mneme mp status      # expect: toee shown as FOREIGN (with the foreign id)
mneme integrate toee # expect: refusal naming the foreign owner; exit non-zero
mneme up toee        # expect: same refusal; owner.yaml NOT re-stamped
```

**Expect**: status flags it foreign (the to-do); both write paths refuse; `owner.yaml`
unchanged. Restore the id afterward.

## Scenario 6 — ambiguity never silently resolves (SC-003)

Create a same-named, this-mneme-owned campaign in both trees (e.g. an extra `toee/` under the
monorepo, integrated to this mneme).

```bash
mneme mp status      # expect: both toee entries listed, by full path
mneme up toee        # expect: ambiguity error naming both trees; no side effect
```

## Scenario 7 — Brick Test / cross-machine model (SC-008)

- Note the minted `mneme.id` from `hypostasis.yaml`.
- Simulate a fresh runtime: a clean config that reuses the **same** `mneme.id` pointed at the
  same trees. `status` classifies the previously-claimed campaigns as `OWNED` (re-adopted
  from `owner.yaml` alone, no central registry).
- Repeat with a **different** `mneme.id` → the same campaigns classify as `FOREIGN`.

## Regression

```bash
pytest tests/unit tests/integration
```

**Expect**: all green, including the single-tree backward-compat tests.
