# Quickstart: validating Portable vs Host-Local Campaign State

End-to-end validation that the feature works. Each scenario maps to a success criterion
(SC-00x) in [spec.md](./spec.md). Assumes the `006-portable-campaign-state` branch checked out
and the package installed in the dev venv. Implementation lives in `tasks.md`.

Scenarios 1–6 are synthetic and run on one machine. Scenario 7 is the live fleet.

## Prerequisites

- A campaigns tree with at least two campaigns, one carrying a legacy `store.path`.
- A second "host" is simulated by a second `hypostasis.yaml` with a different
  `data_roots.mempalace` — that is the only variable that matters, since the bug is entirely
  about a path that differs per host.

```yaml
# hostA.yaml
data_roots:
  campaigns: [~/tmp/006/trees/main]
  mempalace: ~/tmp/006/hostA/.mempalace
# hostB.yaml — same trees, different palace root, NO mneme: block
data_roots:
  campaigns: [~/tmp/006/trees/main]
  mempalace: ~/tmp/006/hostB/.mempalace
```

## Scenario 0 — the #35 prerequisite

```bash
ln -s /mnt ~/tmp/006/trees/main/mnt
time mneme mp status --config hostA.yaml
rm ~/tmp/006/trees/main/mnt
```

**Expect**: completes in under a second. Before GH #35 is fixed this recurses the whole
filesystem and hangs — and 006 puts a tree scan on three more code paths, so this must pass
before anything below is meaningful.

## Scenario 1 — the authority carries no path (SC-005)

```bash
mneme mp bringup demo --config hostA.yaml
grep -A3 '^store:' ~/tmp/006/trees/main/demo/.mneme/mempalace.yaml
```

**Expect**:

```yaml
store:
  alias: demo
```

No `path:` line. Confirm the resolved store was nonetheless created at
`~/tmp/006/hostA/.mempalace/palaces/demo`.

## Scenario 2 — identical bytes, different resolved paths (SC-002, SC-003, FR-017)

```bash
sha256sum ~/tmp/006/trees/main/demo/.mneme/mempalace.yaml   # record
mneme mp render demo --config hostB.yaml
sha256sum ~/tmp/006/trees/main/demo/.mneme/mempalace.yaml   # unchanged
mneme mp status --config hostB.yaml | grep demo
```

**Expect**: the checksum is identical before and after — host B does not "correct" host A's
file. Host B's status shows the store resolved under `~/tmp/006/hostB/.mempalace`. This is the
inverse of the reported bug, where the two hosts flipped the file back and forth forever.

Then check the store-naming faces still agree on each host separately (FR-015 — 003's "right
store everywhere", now per-host):

```bash
mneme mp status --config hostB.yaml | grep 'demo.*faces'
grep -A3 mempalace ~/tmp/006/trees/main/demo/.mcp.json
```

**Expect**: `faces: right store everywhere` under host B, with `.mcp.json` and host B's
`config.json` naming `~/tmp/006/hostB/.mempalace/palaces/demo`. Re-render under host A and
confirm host A's faces name host A's root — each host's faces are correct for that host, and
neither is a tracked file that the other will fight over.

## Scenario 3 — the adopt-or-mint decision (SC-004)

Host B has no `mneme:` block, and `demo` is owned by host A's identity.

```bash
mneme up demo --config hostB.yaml
```

**Expect**: refusal, not a mint. The message names host A's id, the campaigns carrying it, and
both remedies. Verify `hostB.yaml` still has **no** `mneme:` block — the refusal wrote nothing.

```bash
mneme identity show  --config hostB.yaml     # "not established" + the same two remedies
mneme identity adopt <hostA-id> --config hostB.yaml
mneme mp status --config hostB.yaml | grep demo   # now OWNED
```

Then check the greenfield path still works: point a third config at an empty tree and confirm
`mneme integrate` mints and reports an id (FR-003).

## Scenario 4 — legacy `store.path`, both cases (SC-007)

Hand-add a `path:` line to `demo`'s authority.

```bash
# case A: equal to the derived location
mneme mp status --config hostA.yaml | grep demo
# case B: a different location
mneme mp status --config hostA.yaml | grep demo
mneme mp render demo --config hostA.yaml
```

**Expect**: case A loads and shows a to-do row saying to remove the field. Case B fails on
*every* operation, read-only included, with an error naming both locations — and the fleet
status still reports every other campaign in full (FR-014a). Verify no store directory was
created or touched during case B.

## Scenario 5 — ownership applies to every route (SC-008)

```bash
mneme mp render demo --config hostB.yaml --dir ~/tmp/006/trees/main/demo
```

Run this **before** the adoption in Scenario 3. **Expect**: refused with the ownership message.
Before 006 this succeeded — `--dir` skipped the gate as a side effect of sharing `find()`, and
it was the only workaround for the reported bug. It must no longer be one.

## Scenario 6 — duplicate alias (SC-008)

Give two campaigns the same `store.alias`.

```bash
mneme mp status  --config hostA.yaml
mneme mp render  demo --config hostA.yaml
```

**Expect**: any operation touching either campaign fails, naming both campaigns and the shared
alias. Neither store is read or written while the conflict stands.

## Scenario 7 — the live fleet (SC-001, SC-006)

The real migration. Both `~/campaigns/toee` and `~/campaigns/obelisk` are owned by
`64cf8b36-e823-4b8e-8353-d08fe707f9be`; this host's config currently names `c82056d4-…`, which
owns nothing.

```bash
mneme identity adopt 64cf8b36-e823-4b8e-8353-d08fe707f9be
```

Then remove the one legacy line from each authority in the `~/campaigns` repo — `obelisk`'s
names the other host's `$HOME` and is fatal here until it goes; `toee`'s is the to-do row.
Commit both in that repo; the edit and the release are one deployment (each host finds a
*different* campaign fatal, so a half-deployed fleet has one broken campaign per machine).

```bash
mneme mp status                    # both campaigns OWNED, faces "right store everywhere"
mneme mp render obelisk --check    # coherent WITHOUT --dir  ← the GH #51 repro
mneme mp render toee    --check
git -C ~/campaigns diff            # empty — no host-attributable churn
```

**Expect**: the `--check` that previously failed with *"exists only as foreign-owned copies"*
now passes with no flags, and the repository stays clean across repeated runs on either
machine.

## Regression

```bash
pytest tests/unit tests/integration
ruff check .
```

**Expect**: all green, including the 002-era authorities with no store block at all, and the
single-host configs that declare no `data_roots.mempalace`.
