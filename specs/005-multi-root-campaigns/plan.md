# Implementation Plan: Multi-Root Campaign Discovery & Membership

**Branch**: `005-multi-root-campaigns` | **Date**: 2026-06-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/005-multi-root-campaigns/spec.md`

## Summary

Today mneme assumes one managed root == one git tree, and campaigns are its immediate
subdirectories (`mneme/mempalace/discover.py:47`, scalar `data_roots.campaigns`). This
feature makes the campaigns location a **list of trees**, discovers campaigns across all
of them, and adds a **host-independent ownership model**: each campaign self-declares its
owning mneme in `.mneme/owner.yaml`, claimed by an explicit `mneme integrate` step that
precedes full `mneme up`. Discovery and status stay strictly read-only; foreign-owned
campaigns are surfaced, never silently managed or re-stamped. The mneme identity is a
generated, host-independent UUID (+ optional label) in `hypostasis.yaml`, so the same
logical mneme can later bring a campaign up from a different physical machine.

Technical approach: normalize `data_roots` values to tuples (scalar stays valid → 1-tuple),
generalize discovery/resolution over many trees, add an `ownership` module + `owner.yaml`
read/classify/write, add a `mneme identity` field to the hypostasis authority with a
one-time lazy mint, and add a `mneme integrate` CLI command. No new daemon, no second
authority — reuse the existing YAML-authority + render patterns.

## Technical Context

**Language/Version**: Python 3.11+ (existing `hypostasis` + `mneme` packages)

**Primary Dependencies**: PyYAML (config I/O), Typer (CLI), stdlib `uuid`, `pathlib`,
`dataclasses`. No new runtime dependency.

**Storage**: YAML/JSON files only — `hypostasis.yaml` (the one config authority),
per-campaign `.mneme/owner.yaml` (new) and `.mneme/mempalace.yaml` (existing). No database.

**Testing**: pytest (`tests/unit`, `tests/integration`), existing fixtures in
`tests/fixtures/__init__.py`.

**Target Platform**: Linux/WSL CLI (operator workstation + DGX); offline-capable.

**Project Type**: Single project — CLI + library (`hypostasis/`, `mneme/`).

**Performance Goals**: Discovery over a handful of trees with tens of campaigns is
sub-second; correctness and determinism matter, not throughput.

**Constraints**: Discovery + status MUST be read-only and offline (no git network, no
writes to any campaign — FR-014, SC-005). Deterministic ordering (FR-010). Backward
compatible with scalar `data_roots.campaigns` (FR-002). `owner.yaml` carries no host
coordinate (FR-013/019).

**Scale/Scope**: Personal fleet — 1–10 trees, tens of campaigns. One logical mneme today;
data model must not preclude the same identity on multiple runtimes (FR-019).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Tested against Principles I–IX and the five anti-patterns:

- **I. Silicon Truth** ✅ — discovery/status observe the live on-disk checkout and never
  write (FR-014); ownership is classified by reading `owner.yaml`, not by a cached claim.
  *Kills Optimistic Lies.*
- **II. Sovereign Identity** ✅ — mneme identity is a generated UUID, explicitly **not**
  host-derived (FR-012/019); `owner.yaml` names no machine/path. *Kills Infrastructure
  Proxy* — this is the whole point of the cross-machine requirement.
- **III. Intrinsic State** ✅ — ownership travels inside the campaign (`.mneme/owner.yaml`),
  not in a side registry. Moving a campaign between trees keeps its owner (FR-013, US4-6).
- **IV. Transient Viewer / Brick Test** ✅ — a fresh mneme with the same identity re-adopts
  its campaigns from their `owner.yaml` alone, no central store to restore (FR-018, SC-008).
- **V. One Authority, No Split-Brain** ✅ — the trees list and identity live in the single
  `hypostasis.yaml` authority (FR-011); no second writable store. Foreign-owned campaigns
  are refused, never re-stamped (FR-015) — the explicit anti-split-brain rule. `owner.yaml`
  is the *single* owner authority per campaign (one writer: integrate/up).
- **VI. Federated, input[∞]** ✅ — per-tree discovery, one unreachable/odd tree doesn't
  wedge the run; no central counter/lock. Ambiguity surfaced, not globally serialized.
- **VII. Logical Datasets** ✅ — a tree is modeled as a *coordinate* (checkout location),
  a campaign/owner as *identity*; changing where a tree lives doesn't change logic.
- **VIII. Transform the Constraint** ✅ — the hard "which single tree?" problem is removed
  by dropping the single-tree assumption (list of roots) rather than engineering around it;
  reuse the existing render/authority machinery instead of a new daemon/registry.
- **IX. Observability** ✅ — `status` surfaces un-integrated and foreign-owned campaigns and
  name ambiguities (the to-do the operator must act on), not just owned ones.

**Result: PASS, no violations.** Complexity Tracking left empty.

One amendment-adjacent note (not a violation): minting the mneme identity is a **one-time,
targeted write** into `hypostasis.yaml`. To honor "human owns the authority file," the mint
appends only a `mneme:` block when absent and never rewrites existing content (see
research.md R3). This is the single write path for identity and is idempotent thereafter.

## Project Structure

### Documentation (this feature)

```text
specs/005-multi-root-campaigns/
├── plan.md              # This file
├── research.md          # Phase 0 — binding decisions (config shape, identity mint, owner.yaml)
├── data-model.md        # Phase 1 — entities: trees list, MnemeIdentity, Owner, CampaignRef states
├── quickstart.md        # Phase 1 — end-to-end validation (two trees, integrate, foreign-owned)
├── contracts/
│   ├── hypostasis-additions.schema.md   # data_roots list + mneme identity (delta vs 001 contract)
│   ├── owner-yaml.schema.md             # .mneme/owner.yaml format + classification rules
│   └── discovery-and-lifecycle.md       # discover/find + integrate/up CLI command contracts
└── tasks.md             # Phase 2 (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
hypostasis/
├── models.py        # CHANGE: data_roots → dict[str, tuple[Path,...]]; ADD MnemeIdentity + field
├── config.py        # CHANGE: _parse normalizes scalar|list; validate per-element + identity;
│                    #         ADD ensure_mneme_identity() (lazy one-time mint, textual append)
└── render.py        # CHANGE: emit data_roots values as lists; echo mneme identity

mneme/
├── mempalace/
│   ├── discover.py      # CHANGE: campaigns_root→campaigns_roots; discover() over all trees;
│   │                    #         find() multi-tree + ambiguity; CampaignRef gains tree + owner_state
│   ├── ownership.py     # NEW: read_owner / classify / write_owner for .mneme/owner.yaml
│   ├── conform.py       # CHANGE: status rows include membership state (owned/foreign/unintegrated)
│   ├── publish.py       # CHANGE: per-tree git origin (no single global root assumption — FR-009)
│   ├── backup.py        # CHANGE: backups_root via single_root() helper (still single-valued)
│   ├── refresh.py       # CHANGE: iterate refs from multi-tree discover (mostly unaffected)
│   ├── bringup.py       # CHANGE: bring-up integrates first / refuses foreign (FR-017)
│   └── cli.py           # CHANGE: status output; proposals per-tree
├── lifecycle.py     # CHANGE: _campaign_dir resolves across trees; up integrates-then-provisions
└── cli.py           # CHANGE: ADD `mneme integrate` command beside `up`

tests/
├── unit/            # config scalar/list parse + validate; discover multi-tree; find ambiguity;
│                    # ownership classify; identity mint
├── integration/     # status across two trees; integrate writes only owner.yaml; up auto-integrates;
│                    # foreign-owned refused/surfaced
└── fixtures/        # CHANGE: make_entity accepts a tuple of campaign roots + optional identity
```

**Structure Decision**: Single project, existing layout. The one genuinely new module is
`mneme/mempalace/ownership.py` (owner.yaml read/classify/write); everything else is a change
to an existing file. Identity parsing/minting lives in `hypostasis` (the config authority
layer); ownership classification lives in `mneme` (it needs the identity + the campaign dir).

## Complexity Tracking

> No constitutional violations — section intentionally empty.
