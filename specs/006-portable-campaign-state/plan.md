# Implementation Plan: Portable vs Host-Local Campaign State

**Branch**: `006-portable-campaign-state` | **Date**: 2026-08-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/006-portable-campaign-state/spec.md`

## Summary

Feature 005 gave campaigns a host-independent owner identity and made the campaigns
location a list of trees. It missed one axis: two of the files mneme writes into a campaign
are **tracked in git** and carry values that are only true on the machine that wrote them.
`hypostasis.yaml`'s `mneme.id` is minted lazily per host, so a second machine mints its own
UUID and classifies the shared checkout's campaigns `FOREIGN` (`ownership.py:69`,
`discover.py:90-97`). And `authority.py:175` *requires* `store.path` absolute while `:206`
re-serializes the expansion, so the tracked authority flips between `/home/kroussos/…` and
`/home/kostadis/…` forever — each host "correcting" the other.

This feature adds the **portable vs host-local** axis and moves two values across it:

- **Identity becomes adoptable.** When a host has no `mneme:` block, mneme reads the
  `owner.yaml` records already in the declared trees. Exactly one distinct owner → it
  **refuses to mint** and names the adopt remedy. None → mint, as today. More than one →
  refuse and list. Adoption is always an explicit operator act (FR-002/003/004/005). This is
  the Brick Test (Principle IV) applied to the manager's own identity: reconstruct from the
  managed objects, do not re-mint.
- **`store.path` stops being tracked.** The authority carries `store.alias` only; the palace
  location is derived at run time as `<mempalace_root>/palaces/<alias>`, where
  `mempalace_root` is host config (`data_roots.mempalace`, default `~/.mempalace`).
  `to_yaml` never emits a path again, so the field is unwritable by construction (FR-010/011).

Technical approach: no new module for the store half — `StorePointer.path` stays as an
in-memory derived value, so every downstream consumer (`render`, `provision`, `health`,
`backup`, `conform`, `lifecycle`) is untouched; only the parse/serialize boundary in
`authority.py` and the resolution root change. The identity half adds a `mneme identity`
Typer group and one `adopt_mneme_identity()` writer beside the existing
`ensure_mneme_identity()`, reusing its append-don't-rewrite discipline. The clarifications
also make ownership and alias-uniqueness apply to `--dir`-named campaigns (FR-016a/FR-018),
which means moving the ownership check out of `find()` — where it never belonged, since
ownership is not a resolution concern.

## Technical Context

**Language/Version**: Python 3.11+ (existing `hypostasis` + `mneme` packages)

**Primary Dependencies**: PyYAML (config I/O), Typer (CLI), stdlib `uuid`, `pathlib`,
`dataclasses`. No new runtime dependency.

**Storage**: YAML/JSON files only — `hypostasis.yaml` (the one config authority),
per-campaign `.mneme/mempalace.yaml` and `.mneme/owner.yaml`. No database.

**Testing**: pytest (`tests/unit`, `tests/integration`), existing fixtures in
`tests/fixtures/__init__.py`. 125+ tests today; ruff clean.

**Target Platform**: Linux/WSL CLI, two hosts sharing campaign checkouts via git
(`kroussos@` laptop and `kostadis@SiliconValley`, different `$HOME` on each).

**Project Type**: Single project — CLI + library (`hypostasis/`, `mneme/`).

**Performance Goals**: The clarifications put a full tree scan on three code paths that
previously had none (FR-002, FR-016a, FR-018). Discovery over a handful of trees with tens of
campaigns must stay sub-second — which it is **only** once GH #35 is fixed (see Dependencies).

**Constraints**: No tracked campaign file may contain a host-local value (FR-010, SC-005).
Identity is never adopted automatically (FR-005). Establishing identity writes to no campaign
(FR-008). Existing single-host configs need no edit (FR-012). Backward compatible with
002-era authorities that carry no store block at all.

**Scale/Scope**: Personal fleet — 2 hosts, 1–10 trees, tens of campaigns, 2 campaigns
currently mneme-managed (`toee`, `obelisk`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Tested against Principles I–IX and the five anti-patterns:

- **I. Silicon Truth** ✅ — the store location is *resolved* from host config at use time
  rather than read from a stale tracked copy; a legacy path that disagrees with the derived
  one is a hard FAIL naming both (FR-014), never a silent preference for one. *Kills the
  Optimistic Lie* where `obelisk` looked configured and failed with `Permission denied`.
- **II. Sovereign Identity** ✅ — **this is the principle the bug violated.** `$HOME` is an
  infrastructure coordinate; embedding it in a campaign's tracked authority made the
  campaign's identity depend on the host that wrote it. The fix injects the coordinate from
  config (`data_roots.mempalace`) and leaves the campaign naming only *what it needs* — the
  alias. Symmetrically, a fleet identity that cannot leave one host is "a hostname with extra
  steps." *Kills Infrastructure Proxy.*
- **III. Intrinsic State** ✅ — ownership and indexing authority still travel inside the
  campaign. What leaves is only the part that was never intrinsic: where *this machine* keeps
  its palaces. No side registry is introduced; FR-011a explicitly forbids a per-alias override
  table (that would be exactly the hand-synced parallel truth this principle kills).
- **IV. Transient Viewer / Brick Test** ✅ — the load-bearing principle for Part A. "When it
  restarts it *reconciles* — it adopts existing objects with their original identity and
  history; it does not re-mint them as new." Today's lazy mint re-mints the *manager*, which
  is the same failure one level up. FR-002 makes a fresh mneme reconstruct its identity from
  the campaigns it manages.
- **V. One Authority, No Split-Brain** ✅ — the tracked authority and the host config stop
  overlapping: exactly one of them holds each value. FR-011a keeps root-plus-alias as the only
  resolution rule. FR-016 refuses two campaigns sharing one store rather than letting them
  commingle. *Kills Split-Brain* — the ping-pong diff **is** two stores of truth disagreeing.
- **VI. Federated, input[∞]** ✅ — FR-014a is this principle applied to the new failure mode:
  one unloadable campaign is one bad row, not a wedged fleet status. An absent tree still
  contributes nothing without failing the run (existing `discover.py:71-74`).
- **VII. Logical Datasets** ✅ — the campaign names the palace by *meaning* ("the store called
  `obelisk`"); the path is the current encoding of that meaning, resolved by the one component
  that knows the encoding. Changing where a host keeps palaces rewrites no logic above it.
- **VIII. Transform the Constraint** ✅ — the hard problem ("how do two hosts agree on an
  absolute path?") is **deleted** rather than engineered around: nothing needs to agree once
  the path isn't stored. Likewise FR-011a's escape hatch is a filesystem symlink, not new
  machinery. No migration command is built for a two-line edit.
- **IX. Observability** ✅ — a legacy-but-matching path is reported as owed cleanup (FR-013);
  the identity refusal states *what decision is owed* and both remedies (FR-002/009), rather
  than a `FOREIGN` error that "points nowhere."

**Result: PASS, no violations.** Complexity Tracking left empty.

Two amendment-adjacent notes (not violations):

1. **A one-time targeted write to `hypostasis.yaml`.** Adoption writes the operator's config
   file, as 005's mint already does. It keeps the same discipline — append when absent,
   replace only the `mneme:` block when present, never rewrite the file (research R1).
2. **A deliberate breaking change.** FR-018 removes the `--dir` ownership bypass, which is the
   only workaround available today. FR-019 requires the identity remedy to ship in the same
   release so no window exists where a legitimately-owned campaign is unmanageable by both
   routes. This is a constraint on sequencing, tracked in tasks, not a principle violation.

### Post-design re-check (after Phase 1)

Re-evaluated against the design artifacts. **Still PASS, no violations.** Two design choices
were checked specifically because they could have introduced one:

- **Keeping `StorePointer.path` as a derived field** (research R4) could read as retaining the
  offending value. It does not: the value is computed, never read from tracked state, and
  `to_yaml` has no serializer for it — the Principle V guarantee is structural, not a
  convention. Removing the field would have churned nine consumer modules for no behavioral
  gain, which Principle VIII names as the wrong trade.
- **`owner_ids()` gathering evidence across the trees** could read as a registry (Principle
  III/IV). It is not persisted, not cached, and not consulted for anything but a single
  operator-facing decision; the campaigns remain the only record of ownership.

## Project Structure

### Documentation (this feature)

```text
specs/006-portable-campaign-state/
├── plan.md              # This file
├── research.md          # Phase 0 — binding decisions (R1–R6)
├── data-model.md        # Phase 1 — StorePointer, store root, identity lifecycle, states
├── quickstart.md        # Phase 1 — two-host validation + the live-fleet migration
├── contracts/
│   ├── mempalace-yaml.schema.md    # authority store block after the change (delta vs 003)
│   ├── identity-lifecycle.md       # show/adopt/mint + the adopt-or-mint decision table
│   └── hypostasis-additions.schema.md  # data_roots.mempalace (delta vs 005 contract)
├── checklists/
│   └── requirements.md  # spec quality checklist (16/16)
└── tasks.md             # Phase 2 (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
hypostasis/
├── config.py        # ADD mempalace_root(entity) via existing single_root() (:68);
│                    # ADD adopt_mneme_identity() beside ensure_mneme_identity() (:323)
└── models.py        # (no change — MnemeIdentity and data_roots already fit)

mneme/
├── mempalace/
│   ├── authority.py     # CHANGE: _parse derives store.path from root+alias (:94-104);
│   │                    #   validate inverts the absolute rule (:172-176);
│   │                    #   to_yaml emits alias only (:205-206); load() takes mempalace_root
│   ├── ownership.py     # ADD owner_ids(dirs) — read-only evidence for the adopt decision
│   ├── discover.py      # CHANGE: ownership check moves OUT of find() (:90-97) so --dir is
│   │                    #   no longer a bypass (FR-018); ADD alias-uniqueness check (FR-016a)
│   ├── conform.py       # CHANGE: legacy-path to-do row (FR-013); UNVERIFIABLE note now says
│   │                    #   adopt-or-mint (:141-145); config_json via mempalace_root (:117)
│   ├── bringup.py       # CHANGE: _default_store + default_config_json use mempalace_root
│   ├── bootstrap.py     # CHANGE: _default_store uses mempalace_root (:35)
│   ├── backup.py        # CHANGE: thread mempalace_root into authority.load (:40, :114)
│   ├── publish.py       # CHANGE: same threading (:52, :62, :150)
│   ├── cli.py           # CHANGE: same threading (:162); status renders the new rows
│   └── models.py        # CHANGE: docstring — StorePointer.path is derived, never serialized
├── mcp/server.py    # CHANGE: thread mempalace_root into authority.load (:32, :77, :111)
└── cli.py           # ADD `mneme identity` group (show/adopt/mint); CHANGE _ensure_identity
                     #   (:65-71) to the adopt-or-mint resolver; ownership gate on up (:120-128)

hypostasis.example.yaml  # DOCUMENT data_roots.mempalace; rewrite the mneme: block comment
                          #   (:19-21) to say a second host COPIES this block, never mints

tests/
├── unit/            # authority round-trip without path; to_yaml emits no path; conflicting
│                    #   legacy path raises; adopt-or-mint resolver decision table;
│                    #   adopt_mneme_identity preserves file content
├── integration/     # two hosts, identical bytes, different resolved paths; --dir refuses a
│                    #   foreign campaign; duplicate alias refuses; status shows the to-do
└── fixtures/        # CHANGE: make_entity accepts an optional mempalace root
```

**Structure Decision**: Single project, existing layout, **no new modules**. Part B is a
change at one boundary (`authority.py`'s parse/serialize) plus mechanical threading of a root
through existing `load()` call sites — deliberately chosen over introducing a resolver service,
because keeping `StorePointer.path` as a derived in-memory field leaves all nine consumer
modules untouched. Part A adds one function to `hypostasis/config.py` (the config-authority
layer, where 005 put minting) and one Typer group to `mneme/cli.py`; the evidence-gathering
helper goes in `ownership.py` beside the existing `read_owner`.

## Dependencies

**GH #35 is a hard prerequisite.** Discovery treats symlinked children as campaigns and
`rglob`s without bound, so a campaigns root containing `~/campaigns/mnt -> /mnt/` turns
discovery into a full-filesystem scan. Three of this feature's requirements newly depend on a
tree scan (FR-002 identity evidence, FR-016a alias uniqueness, FR-018 ownership on `--dir`
paths). This host is currently clean — no symlinks under `~/campaigns` — but the feature must
not ship a hang onto a host that isn't. Sequenced as the first task.

**Migration ordering.** Under FR-014 each host finds a *different* campaign fatal — the one
naming the other host's `$HOME`. The campaign-repo edit and the release are one deployment.

## Complexity Tracking

> No constitutional violations — section intentionally empty.
