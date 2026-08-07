# Contract: `.mneme/mempalace.yaml` store block (delta vs 003)

The per-campaign indexing authority is unchanged in role and in every field except one. This
contract states the store block's format after 006 and the rules for reading an authority
written before it.

## Format (after 006)

```yaml
# <campaign>/.mneme/mempalace.yaml
campaign: obelisk
recipe_version: 2.0.0
store:
  alias: obelisk          # the ONLY store field. Portable — true on every host.
wings:
  - name: narrative
    source: docs/chapters
    trust: authoritative
    rooms: [...]
  # ...
```

**`store.path` is no longer part of this file.** It was removed because it encoded the writing
host's `$HOME`, which made a tracked file host-specific (FR-010).

## Format (before 006 — accepted, reported)

```yaml
store:
  alias: obelisk
  path: /home/kostadis/.mempalace/palaces/obelisk   # legacy; see the read rules
```

## Resolution

The palace location is **derived, never stored**:

```
palace = <mempalace_root> / "palaces" / <store.alias>
```

`mempalace_root` comes from the host's config authority (`data_roots.mempalace`, default
`~/.mempalace`) — see `hypostasis-additions.schema.md`. Root-plus-alias is the **only**
resolution rule; there is no per-alias override in any authority (FR-011a). A palace that must
live elsewhere is redirected with a filesystem symlink at the derived location, which mneme
follows transparently.

## Read rules

| tracked `store` block | outcome |
|---|---|
| absent entirely | `store = None`. 002-era authorities keep loading; `require_store` still gates bring-up. |
| `alias` only | derive the path. Normal. |
| `alias` + `path`, **resolving equal** to the derived location | loads; fleet status reports a to-do: remove the field (FR-013). |
| `alias` + `path`, **resolving different** | `AuthorityError` naming both locations. Applies to **every** operation on that campaign, read-only included (FR-014). |
| `path` without `alias` | the alias defaults to the campaign name, as today (`authority.py:97`); the path is then judged by the rules above. |

Both sides are symlink-resolved before the equal/different comparison, so a sanctioned
redirect never reads as a conflict.

## Write rules

- **`to_yaml` emits `{"alias": ...}` and never a path.** This is the enforcement point for
  SC-005 — no code path can write a host-local location into a tracked file, because no
  serializer for it exists.
- Reading an authority and writing it back MUST be a fixed point on every host: identical
  input bytes produce identical output bytes regardless of `$HOME` (FR-017, SC-003).
- mneme never rewrites a campaign's authority to *remove* a legacy path. That is the
  operator's one-line edit; status names the owed work rather than performing it (Principle
  IX, and a read path must not write a tracked file).

## The store-naming faces

Three rendered faces name the store, and all three read the resolved location rather than a
tracked one (FR-015). Because the location is now derived per host, each face is correct on
whatever host rendered it, and 003's **"right store everywhere"** coherence property (SC-008
there) holds *within* a host without requiring two hosts to agree on a string:

| face | what it carries | rendered by |
|---|---|---|
| root wing `mempalace.yaml` (cli_pointer) | the **alias** — already portable, unchanged | `render.write_all` |
| `~/.mempalace/config.json` `palaces` map | alias → resolved location | `render.render_global_alias` |
| `.mcp.json` `MEMPALACE_PALACE_PATH` | resolved location | `render.render_mcp` |

The latter two are **host-local by nature** — one is under the host's mempalace root, the other
is untracked in the campaigns repo today. Neither may become tracked without re-introducing
this feature's bug; that is the constraint 006 places on GH #30's tracking decision.

`faces_coherent` compares each face against the *resolved* location, so a coherence check run
on either host passes against that host's own render.

## Alias invariants

- The alias is normalized by the existing `_normalize_wing_name` rule (lowercase, `-`/space →
  `_`) and defaults to the campaign name.
- **No two campaigns may declare the same alias.** Since the location derives from the alias,
  a duplicate means two campaigns resolve to one store. Any operation touching either campaign
  fails, naming both campaigns and the shared alias (FR-016). Because the alias defaults to the
  campaign name, this is the same condition 005 already refuses as a cross-tree name ambiguity
  — now with a second reason.
- Uniqueness is a **fleet-level** invariant, so a single-campaign command consults discovery to
  enforce it, whether the campaign was named by name or by workspace path (FR-016a).

## Unchanged from 003

Wing ordering (sub-scopes before the enclosing scope), `trust` levels, `dispositions`,
`extra_exclusions`, the `FORBIDDEN_TOP_LEVEL` rule that no derived/observed truth may be stored
here, and the all-problems-at-once validation behavior.
