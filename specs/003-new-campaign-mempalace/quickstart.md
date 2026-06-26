# Quickstart & Validation: Mempalace Bring-Up for a New Campaign

Runnable scenarios proving the feature end-to-end, mapped to the spec's Success Criteria.
Implementation lives in `tasks.md`; this is the validation guide.

## Prerequisites

- `pip install -e '.[dev]'` in `~/src/mneme` (provides `mneme`, extends the 002 `mneme mp` group).
- A `hypostasis.yaml` with `data_roots.campaigns` (and a backups location). For real runs, `mempalace`
  at its pin + the embedding endpoint reachable; tests use the **extended stub `mempalace`** (honors
  `--palace`, creates a fake `turbovec/<coll>/store.sqlite3` on `mine`, answers `status`).
- A **new** campaign fixture: a workspace with documents and **no** `.mneme/` config (greenfield).

---

## Scenario A — End-to-end bring-up (US1 → SC-001, SC-002)

```bash
mneme mp bringup stormhaven --dry-run     # show steps + faces; provision/mine/backup nothing
mneme mp bringup stormhaven               # configure → render 4 faces → provision → first-mine → backup
mneme mp status stormhaven                # built / conformant — NOT missing_config
```

**Expect**: the four faces exist (`.mneme/mempalace.yaml` authority with a `store` pointer; rendered
`mempalace.yaml palace:`; `config.yaml mempalace:`; merged `~/.mempalace/config.json` entry; `.mcp.json`
mempalace server); the store dir exists with `turbovec/*/store.sqlite3`; the bring-up report shows each
step's observed outcome; status is green (SC-002). A campaign with no docs reports "nothing to index
yet," not a failure.

---

## Scenario B — Right store everywhere: CLI-by-directory + the MCP (US5 → SC-008)

```bash
cd <campaigns-root>/stormhaven && mempalace status   # walks up to mempalace.yaml palace: → stormhaven store
mneme mp status stormhaven                            # asserts cli_pointer and the .mcp.json face agree on the store
```

**Expect**: from inside the campaign dir the CLI resolves to **stormhaven's** store (not the default
`chat`); the `.mcp.json` mempalace server targets the same store; **zero** wrong-store resolutions.
A campaign whose `palace:` face is removed is flagged by status (the toee/stormgiants bug, #21).

---

## Scenario C — Bindings backup / restore without re-embedding (US3 → SC-004)

```bash
mneme mp backup stormhaven                 # copies turbovec/*/store.sqlite3 + knowledge_graph.sqlite3
ls <backups>/stormhaven/*/turbovec/*/store.sqlite3   # bindings present; NO index.tvim, NO chroma.sqlite3
rm -rf ~/.mempalace/palaces/stormhaven/turbovec       # simulate loss
mneme mp restore stormhaven                # copies bindings back; turbovecdb rebuilds index.tvim, no re-embed
mneme mp status stormhaven                 # built; report says "bindings preserved" (+ any pruning)
```

**Expect**: restore brings the bindings back **without re-embedding** (SC-004); deleted-source entries
are pruned automatically, not served; the stub records **no** embed calls during restore. A from-scratch
re-embed happens only via `mneme mp regenerate --confirm`.

---

## Scenario D — `mneme up` gates on store health (US4 → SC-006)

```bash
mneme up stormhaven                        # OK only if the store is brought up + healthy
rm -rf ~/.mempalace/palaces/stormhaven      # not brought up
mneme up stormhaven                        # FAILS: "mempalace not brought up — run mneme mp bringup"
```

**Expect**: `mneme up` brings up the **runtime** but **fails** (exit 1) if the mempalace store is
missing/unhealthy — it never brings the store up itself (FR-010/014). The failure is reported, not
silent (IX).

---

## Scenario E — Idempotent re-run (US4 → SC-003)

```bash
mneme mp bringup stormhaven                # second run on a healthy campaign
```

**Expect**: a no-op / reported repair — no duplicate store, no clobbered faces, no re-mine of an
up-to-date index. An interrupted first bring-up (kill mid-mine) is reported **not-ready**, never ready.

---

## Scenario F — Brick Test for the index (SC-007)

```bash
rm -rf ~/.mempalace/palaces/stormhaven      # delete the derived store entirely
mneme mp bringup stormhaven                # reproduces an equivalent index from docs + authority alone
```

**Expect**: the index is verifiably **non-authoritative** — re-bringup rebuilds it from the documents +
the in-campaign authority (which survive in version control). No backup required for this to hold.

---

## Success-criteria coverage

| SC | Scenario |
|---|---|
| SC-001 one-command bring-up | A |
| SC-002 immediately observable / conformant | A |
| SC-003 idempotent | E |
| SC-004 restore preserves bindings, no re-embed | C |
| SC-005 one campaign never disturbs another | A, C (config.json merge; per-campaign store) |
| SC-006 `mneme up` catches not-ready | D |
| SC-007 index non-authoritative (Brick Test) | F |
| SC-008 right store everywhere (CLI + MCP) | B |
