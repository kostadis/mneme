# Contract: fleet identity lifecycle (`mneme identity`)

005 gave mneme a host-independent fleet identity but only one way to obtain it — a lazy mint.
That made the identity unreachable from a second host: each machine minted its own, so a
shared checkout's campaigns read as `FOREIGN` everywhere but the machine that claimed them.
This contract defines the identity's lifecycle: it is now **established by adoption or by
minting**, and never invented implicitly when there is something to adopt.

## Commands

Three distinct, discoverable operations (FR-006). `adopt` is the one that makes the identity
portable (FR-001): it establishes an existing fleet id on this host by persisting it in the
host's config authority, preserving the operator's existing file content.

### `mneme identity show`

Read-only. Prints this host's fleet identity and its provenance.

```console
$ mneme identity show
identity: 64cf8b36-e823-4b8e-8353-d08fe707f9be
label:    kostadis-main
source:   ~/.config/hypostasis/hypostasis.yaml
campaigns owned here: toee, obelisk (2 of 2 discovered)
```

With no identity established, it says so and names the choice:

```console
$ mneme identity show
identity: not established
the declared trees contain campaigns owned by 64cf8b36-… (toee, obelisk)
  join that fleet:  mneme identity adopt 64cf8b36-e823-4b8e-8353-d08fe707f9be
  start a new one:  mneme identity mint
```

Exit `0` in both cases — absence of an identity is a reportable state, not an error.

### `mneme identity adopt <id> [--label <label>] [--force]`

Joins an existing fleet by writing `<id>` into the host's config authority. Writes **no
campaign** (FR-008).

- Rejects a malformed id before touching the file.
- If a `mneme:` block is absent, appends one. If present, replaces only that block's lines —
  the operator's comments and the rest of the file are preserved verbatim (research R1).
- **Refuses** when the *current* identity already owns campaigns in the declared trees, naming
  the campaigns that would be orphaned; `--force` overrides (FR-007).
- Idempotent when `<id>` is already this host's identity.

```console
$ mneme identity adopt 64cf8b36-e823-4b8e-8353-d08fe707f9be
adopted fleet identity 64cf8b36-… → ~/.config/hypostasis/hypostasis.yaml
now owns: toee, obelisk

$ mneme identity adopt 11111111-2222-3333-4444-555555555555
FAIL identity adopt: this host's identity c82056d4-… owns 2 campaigns
     (toee, obelisk) — adopting would orphan them. Re-run with --force to proceed.
```

### `mneme identity mint [--label <label>]`

Starts a **new** fleet: generates a fresh id and persists it. Explicit, so it is available
even when evidence to adopt exists — forking is a legitimate choice, it just must be deliberate.

```console
$ mneme identity mint --label laptop-fleet
minted fleet identity 7ac1f0b2-… (new fleet) → ~/.config/hypostasis/hypostasis.yaml
```

## The adopt-or-mint decision

Whenever a command needs an identity and none is established, mneme gathers read-only evidence
— the distinct `mneme.id` values in `.mneme/owner.yaml` across the declared trees — and:

| distinct owner ids found | behavior | exit |
|---|---|---|
| **0** | mint automatically and echo the id (unchanged 005 greenfield behavior) | 0 |
| **1** | **refuse to mint.** Name the id, the campaigns carrying it, and both remedies | non-zero |
| **>1** | **refuse.** List each id with its campaigns; require an explicit choice | non-zero |

```console
$ mneme up obelisk
FAIL up: this host has no fleet identity, and the declared trees contain 2 campaigns
     owned by 64cf8b36-e823-4b8e-8353-d08fe707f9be (toee, obelisk).
     join that fleet:  mneme identity adopt 64cf8b36-e823-4b8e-8353-d08fe707f9be
     start a new one:  mneme identity mint
```

**mneme never adopts on its own** (FR-005). Choosing which fleet a campaign belongs to is an
attribution decision; the system surfaces the evidence and stops. This is the same rule 005
applied to campaigns (no silent take-over, **005** FR-015), applied to the manager's own
identity.

## Ownership refusal messages

Every ownership refusal names three things (FR-009): the campaign's declared owner, this
mneme's identity or its absence, and the next step.

```console
$ mneme mp render obelisk --check
FAIL render: campaign 'obelisk' is owned by 64cf8b36-… ; this mneme is c82056d4-… .
     If this host should join that fleet:  mneme identity adopt 64cf8b36-…
```

Compare today's message, which names neither this mneme's id nor any remedy:

```console
FAIL render: campaign 'obelisk' exists only as foreign-owned copies
     (trees: /home/kroussos/campaigns) — not managed by this mneme
```

## Ownership applies to every route

The 005 workspace-path override (`--dir`, GH #27) resolves a campaign by path and currently
skips ownership as a side effect of sharing `find()`. After 006, ownership is classified in the
command layer and applies to **both** routes (FR-018): `--dir` means only "disambiguate which
tree," never "operate on a foreign campaign."

There is no flag that operates on a foreign campaign. Ownership **transfer** — re-homing a
campaign to a different fleet id — is out of scope for this feature.

## Invariants

- Identity operations write only the host config authority; never a campaign (FR-008).
- `owner.yaml`'s format and its four classification states are unchanged from 005.
- The identity remains a generated UUID with no host coordinate encoded in it (Principle II,
  005 FR-012/019). What changes is that the *same* value can now legitimately reach a second
  host — which is what 005 FR-019 always specified and never delivered.
