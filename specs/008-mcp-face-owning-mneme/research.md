# Research: MCP Face Bound to the Owning mneme (008)

All findings verified against the code on `origin/main` @ 4f20959 and this host on 2026-11-09.

## R1 — Where an owning mneme's programs and config come from

- **Decision**: Bind with `entity.venv / "bin" / "mneme"`, `entity.venv / "bin" / "mempalace-mcp"`
  and `entity.source_path` (the absolute path of the hypostasis.yaml that was loaded).
- **Rationale**: `ConfigEntity` (hypostasis/models.py:89) already carries `venv` (declared in
  hypostasis.yaml) and `source_path` (set by `config.load`). A mneme *is* one hypostasis config, so
  these are exactly "the owning mneme's install and config" — injected from config, never
  hardcoded (Principle II). On this host both binaries exist in `~/.venvs/main/bin/` and are also
  first on PATH, which is why the bare-name defect has been invisible.
- **Alternatives**: `sys.executable`/`sys.argv[0]` of the running process — rejected: describes the
  process doing the render, not the mneme the config declares (a dev checkout running against
  another config would write its own path). `shutil.which` — rejected: that *is* the PATH defect.

## R2 — "Owned by the rendering mneme"

- **Decision (revised during implementation, 2026-11-09)**: the gate is the existing one —
  `discover.resolve()` already refuses a FOREIGN campaign (`foreign_refusal`) on every `mp`
  route, including `mp faces` and bring-up. OWNED, UNINTEGRATED and UNVERIFIABLE campaigns are
  rendered, exactly as the mcp face is rendered today.
- **Why not "OWNED only"**: a brand-new campaign is UNINTEGRATED during bring-up, and bring-up
  already renders its faces; an OWNED-only gate would break bring-up of every new campaign.
- **Two-mneme safety (SC-003) still holds**: a campaign owned by mneme B is FOREIGN to mneme A,
  so A refuses it; the entries A writes always name A's own venv and config.

## R3 — Where the clone root is

- **Decision**: The clone root is `ref.tree`, the declared `data_roots.campaigns` entry the
  campaign was discovered under (discover.py:30), when `ref.path != ref.tree`.
- **Rationale**: on this host every tree *is* a sparse clone root (`~/toee`, `~/phandalin`, …) and
  each campaign is an immediate child. No git calls needed; it is the coordinate the GM already
  declared. A campaign resolved by `--dir` with no tree has no clone root → Stories 1–3 only.
- **Alternatives**: `git rev-parse --show-toplevel` — rejected: adds a git dependency to a
  render, and a tree that isn't a git clone would behave differently from the declared model.

## R4 — What counts as a campaign in the clone (FR-015)

- **Decision (GM, 2026-11-09)**: a host-declared **shared set** in hypostasis.yaml. Every
  checked-out, non-dot, non-symlink immediate child of the clone root whose name is not in the
  shared set is a campaign.
- **Evidence**: the campaigns repo's top level is `.claude Hillsfar Phandalin curse-of-strahd
  experiments gm-assistant greenwold obelisk out-of-the-abyss scripts stormgiants toee`; only four
  carry `.mneme/owner.yaml`, so "has `.mneme/`" misses never-integrated campaigns. Discovery's
  "every child is a campaign" counts `gm-assistant`/`scripts`/`statblocks` (and is why `mp status`
  lists `scripts`/`statblocks` as unintegrated campaigns today).
- **Shape**: top-level key `campaign_shared_dirs: [gm-assistant, scripts, …]` (names, not paths;
  a host-wide list because all clones come from the one campaigns repo). Absent → FR-016: no root
  write, status to-do listing the children found.
- **Not in scope**: using the shared set to stop discovery reporting `scripts`/`statblocks` as
  campaigns. Same definition, but it changes every status/refresh caller → follow-up issue.
- **Alternatives**: declared in the campaigns repo (rejected by GM); `.mneme/` presence (misses
  stormgiants-style checkouts).

## R5 — `mp refresh` does not render faces

- **Finding**: `refresh.py` only mines; faces are rendered by `bringup` (new campaigns) and
  `mp faces` (`render_existing_faces`). Spec FR-010/SC-001 corrected to name `mp faces`.
- **Decision**: keep refresh mining-only; status notes name `mneme mp faces <campaign>`.

## R6 — Status rows

- **Decision**:
  - Existing `faces` row (`State.STALE_RENDER`, a FAIL state) gains the new mismatch reasons for
    the campaign's `.mcp.json` *and*, for a single-campaign clone, the root `.mcp.json`.
  - New `clone` row reporting the clone-root verdict:
    `CONFORMANT` (single campaign; root rendered — coherence itself is in `faces`),
    new `CLONE_ROOT_OWED` (to-do, not FAIL: multi-campaign without mneme entries, or shared set
    undeclared), new `CLONE_ROOT_CONFLICT` (FAIL: multi-campaign *with* mneme-owned root entries).
    No row when the campaign has no clone root.
- **Rationale**: matches the existing split between FAIL states and owed work (`CONSUMERS_OWED`,
  `CORPUS_UNDECLARED`), and keeps "is the file right" (faces) separate from "is the layout
  supported" (clone).

## R7 — No-store campaigns (FR-008)

- **Finding**: `render_faces` skips the global alias and mcp face when `cfg.store is None`.
- **Decision**: split `render_mcp` so the `mneme` entry is written regardless; the `mempalace`
  entry still requires a store. `faces_coherent` likewise checks the `mneme` entry even with no
  store (today it returns early).

## R8 — Writing the server list safely

- **Decision**: read → parse → replace only the `mneme`/`mempalace` keys → write to a temp file in
  the same directory → `os.replace`. Invalid JSON → raise, file untouched. Value preservation of
  other entries is by construction (parsed dicts re-serialized); key order of other entries kept.
- **Note**: "byte-for-byte in value" (FR-006) means values, not whitespace — the existing render
  already re-serializes with `indent=2`.

## R9 — Pre-existing hand-added root entry (`~/obelisk/.mcp.json`)

- **Finding**: has `mneme: /home/kostadis/.venvs/main/bin/mneme …` (hand-added). It is a
  mneme-owned name → replaced on the first `mp faces obelisk`. Recorded in quickstart.
