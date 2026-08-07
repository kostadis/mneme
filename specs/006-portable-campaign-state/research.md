# Phase 0 Research — Portable vs Host-Local Campaign State

Binding decisions for the 006 implementation. Each records what was chosen, why, and what
was rejected. Ground truth was read off the live fleet on 2026-08-07 (both hosts' values are
quoted in the spec's Overview table).

---

## R1 — How adoption writes `hypostasis.yaml`

**Decision.** `adopt_mneme_identity(config_path, id, *, label=None, force=False)` lives in
`hypostasis/config.py` beside `ensure_mneme_identity` (`:323`) and follows its discipline:
read the file as text, and either **append** a `mneme:` block when absent or **replace only
the `mneme:` block's lines** when present. Never a full YAML round-trip rewrite.

**Rationale.** `hypostasis.yaml` is hand-authored and comment-dense — the live file carries
explanatory comments on nearly every key, including the `mneme:` block's own three-line
comment (`hypostasis.example.yaml:19-21`). `yaml.safe_dump` of a parsed document would
silently delete all of them. 005 already solved this for minting (`:334-338`); adoption
reuses the answer rather than inventing a second write path.

**Alternatives rejected.**
- *Full parse-and-rewrite* — destroys the operator's comments; violates "the human owns
  `hypostasis.yaml`."
- *Tell the operator to hand-edit* — that is the status quo, and the status quo is why #51's
  comment says the error "points nowhere." A named verb is what makes the remedy discoverable
  (Principle IX).
- *A separate identity file* — a second authority for one value (Principle V).

**Validation.** `adopt` rejects a malformed id before touching the file (spec Edge Cases), and
refuses when the *current* identity already owns campaigns in the declared trees unless
`--force` (FR-007) — the refusal names the campaigns that would be orphaned.

---

## R2 — What counts as evidence for the adopt-or-mint decision

**Decision.** The evidence is the set of distinct `mneme.id` values found in
`.mneme/owner.yaml` across every campaign in the declared trees, gathered read-only via a new
`ownership.owner_ids(campaign_dirs) -> dict[str, list[str]]` (id → campaign names) built on the
existing `read_owner`. The decision table:

| distinct ids | behavior |
|---|---|
| 0 | mint (unchanged 005 behavior), echo the minted id |
| 1 | **refuse to mint**; name the id, the campaigns carrying it, and both remedies |
| >1 | **refuse**; list each id with its campaigns; require an explicit choice |

**Rationale.** Principle IV states the manager "adopts existing objects with their original
identity and history … it does not re-mint them as new." A lazily-minted UUID on a second host
is exactly a re-mint. But *auto*-adopting would be an attribution decision made by software
about which fleet a campaign belongs to — so the system surfaces the evidence and stops
(FR-005, and consistent with 005 FR-015's "no silent take-over").

**Alternatives rejected.**
- *Auto-adopt when unambiguous* — silently claims an identity the operator may not have
  intended to join; a tree containing someone else's campaign would take over their id.
- *Never mint; always require an explicit verb* — breaks the greenfield first-run experience
  005 shipped, for no safety gain when there is nothing to adopt.
- *Derive identity from a shared secret or the git remote* — reintroduces an infrastructure
  proxy (Principle II) and couples identity to a coordinate that can change.

**Consequence.** This puts a tree scan on the identity path, which previously did none. See R6.

---

## R3 — Where the store root lives, and its default

**Decision.** `data_roots.mempalace`, single-valued, read through the **existing**
`config.single_root(entity, key)` helper (`config.py:68-78`) — the same mechanism
`backup.backups_root` already uses for `data_roots.backups` (`backup.py:32-34`). Absent →
default `~/.mempalace`. New helper `config.mempalace_root(entity) -> Path`.

**Rationale.** It is a host coordinate, so it belongs in the host's one config authority
alongside the other data roots (Principle II — injected, never hardcoded). Reusing
`single_root` means it inherits the existing "declared with more than one path" error and the
existing absolute-path validation (`config.py:280-285`) for free. Defaulting preserves FR-012:
no existing single-host config needs an edit.

**Alternatives rejected.**
- *A top-level `mempalace_root:` key* — a second shape for the same kind of value;
  `data_roots` is where paths already live.
- *Reading it from `~/.mempalace/config.json`* — that file is mempalace's, and mneme treating
  it as an authority is precisely the Fragmented State #29/#31 complain about.
- *No config at all, always `~/.mempalace`* — a hardcoded infrastructure coordinate in
  component logic (Principle II), and it forecloses moving palaces to another disk.

**Bonus.** Three existing hardcodes retire into this helper: `bringup.default_config_json`
(`:27`), `bringup._default_store` / `bootstrap._default_store` (`:31` / `:35`), and
`conform.py:117`.

---

## R4 — Keep `StorePointer.path` as a derived field, or remove it

**Decision.** **Keep it**, redefined as derived and in-memory-only. `authority._parse`
computes `path = mempalace_root / "palaces" / alias`; `to_yaml` emits `alias` alone.
`authority.load()` grows `*, mempalace_root: Path | None = None`, defaulting to
`~/.mempalace`, threaded from `config.mempalace_root(entity)` at the ~12 call sites that have
an entity in scope.

**Rationale.** `cfg.store.path` is read by nine call sites across six modules (`render.py:184`,
`:207`, `:238`; `provision.py:26-32`; `health.py`; `backup.py:38-41`; `conform.py:99`;
`lifecycle.py:85`; `cli.py:491-503`). Removing the field would rewrite every one of them to
take a resolver. Keeping it derived confines the change to the parse/serialize boundary, which
is where the bug actually is. The safety property that matters — *the field can never be
written to a tracked file* — is enforced by `to_yaml`, not by the field's existence (SC-005).

**Consequence for FR-015.** The three store-naming faces (`render.py:184` global alias, `:207`
MCP, `:238` the coherence check) keep reading `cfg.store.path` unchanged and therefore render
the *resolved* location automatically — 003's "right store everywhere" property is preserved
with no edit to `render.py`. It becomes a **per-host** property: each host's faces name that
host's root, which is correct precisely because those two faces are not tracked in the campaign
repo. See `contracts/mempalace-yaml.schema.md` § *The store-naming faces*; this is also the
constraint 006 places on GH #30's tracking decision.

**Alternatives rejected.**
- *Remove `path`; add `store_path(cfg, entity)`* — architecturally purer, nine modules churned
  for no behavioral gain. Complexity is Cost (Principle VIII).
- *Keep the path tracked but `~`-relative* — the smaller change, and it was on the table until
  the design question was answered: it still stores a location in a portable-only-by-luck form,
  and any non-`$HOME` store re-breaks it. Rejected in favor of the alias being the single truth.

---

## R5 — Handling a legacy `store.path` in an existing authority

**Decision.** Three cases, clarified 2026-08-07:

| tracked `store.path` | behavior |
|---|---|
| absent | normal; nothing to report |
| present, **resolves equal** to the derived location | loads fine; `mp status` reports a to-do row: remove the field (FR-013) |
| present, **resolves different** | `AuthorityError` naming both locations, on **every** operation including read-only ones (FR-014). Status shows that campaign as invalid-config and every other campaign in full (FR-014a) |

Comparison resolves symlinks on both sides before declaring a conflict, so the sanctioned
redirect of FR-011a never reads as a mismatch.

**Rationale.** A conflicting path means a real store may exist at the tracked location with
real content in it. Silently switching to the derived location would abandon it — the same
class of failure as #26's silent embedder swap. Failing closed everywhere is the strictest
option and was chosen deliberately over "fail only on store-touching operations."

**Live consequence.** Each host finds a *different* campaign fatal: this host loses `obelisk`
(tracked `/home/kostadis/…`), the other loses `toee` (tracked `/home/kroussos/…`). Removing
both fields fixes both hosts. Hence the migration and the release are one deployment.

**Alternatives rejected.**
- *Warn and prefer the derived path* — silently orphans a populated store.
- *Prefer the tracked path when it exists* — preserves the ping-pong the feature exists to kill.
- *Auto-remove the field on load* — a read path that writes to a tracked file; also hides the
  conflict case entirely.

---

## R6 — Where the ownership and alias-uniqueness checks live

**Decision.** Move the ownership classification **out of** `discover.find()` (`:90-97`) into
the command layer, applied to whatever `resolve()` returns — by name or by `--dir`. Add an
alias-uniqueness check over the discovered set, also applied to both routes (FR-016a).

**Rationale.** `find()` is name resolution; ownership is membership. Conflating them made
`--dir` an accidental ownership bypass (#51's comment: "any future change that moves the
ownership check out of `find()` — which is arguably where it belongs — silently removes the
only workaround"). This feature removes the *need* for that workaround, which is the only
point at which closing the bypass is safe. Alias uniqueness is fleet-level by nature, so it
must consult discovery even for a single-campaign command.

**Alternatives rejected.**
- *Leave the bypass and only forbid documenting it* — an undocumented silent-take-over path
  surviving inside a feature whose thesis is "no silent take-over."
- *Add a named `--force-owner` flag* — that is ownership **transfer**, explicitly out of scope
  (spec Out of Scope; GH #51 comment treats it as separable).

**Consequence — this is the #35 dependency.** Three paths now scan the trees where none did
before (R2's identity evidence, alias uniqueness, and ownership on `--dir`-named campaigns).
On a host whose campaigns root contains a symlink such as `~/campaigns/mnt -> /mnt/`,
`discover()` recurses the whole filesystem and hangs. **GH #35 must land before or with this
feature**; it is sequenced as the first task. This host is currently clean (verified
2026-08-07 — no symlinked entries under `~/campaigns`), which is why the hazard is latent
rather than blocking.
