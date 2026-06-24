# Platform re-architecture plan (Spec Kit umbrella)

> **Status: scaffold stood up; constitution + first spec not yet authored.**
> Updated 2026-06-24. This is the working plan for `~/src/platform`, the umbrella
> repo that owns the **integration / distribution / orchestration plane** only.
> Component repos keep doing their jobs; `platform` owns how they're declared,
> installed, wired, and version-pinned.

## Current state (2026-06-24)

What exists on disk:

- `~/src/platform/` — `git init` done, branch `master`, **no commits yet**.
- Spec Kit scaffold from `specify init` now at the **repo root** `~/src/platform/`
  (`.specify/` templates + scripts, `.claude/skills/speckit-*`, stub `CLAUDE.md`).
  The earlier `platform/platform/` nesting was un-nested 2026-06-24; scripts
  resolve the repo root via git, so the move was clean.
- `.specify/memory/constitution.md` — **still the unfilled template** (placeholders).
- **No `specs/` directory** — no `001-…` spec created.
- **No `platform.yaml`, no installer, no status tool.**

Net: scaffolding only. None of the precision work (constitution principles,
the `001` spec body, the config schema) has been authored. That is the next step
and it is *yours* to author, not the LLM's to invent.

## Progress checklist

- [x] Decide approach: Spec Kit via umbrella `~/src/platform` (advisory accepted).
- [x] `git init` the umbrella repo.
- [x] `specify init` — scaffold present.
- [x] Resolve the `platform/platform/` nesting — un-nested to repo root 2026-06-24.
- [x] First commit (scaffold + constitution + plan) — 2026-06-24, `bd4567c` on `master`.
- [x] Author the constitution — done 2026-06-24, distilled from the Kostadis Engine
      lenses (Tribunal/Anti-Gravity/Lagrange/Value-Bridge) into 8 principles +
      economic + human-checkpoint sections. v1.0.0 at `.specify/memory/constitution.md`.
      (Principle V — "One Entity, One Database — No Split-Brain, No Stale Copies" —
      added from Kostadis's single-DB-per-entity rule, not in the original lenses;
      strengthened to cover runtime cache coherence, not just restore.)
      (Authored directly from the doctrine rather than via `/speckit.constitution`'s
      interview, per "human owns structure.")
- [x] `/speckit.specify 001-reproducible-install` — **DONE 2026-06-24** on branch
      `001-reproducible-install`. `specs/001-reproducible-install/spec.md` (14 FRs,
      4 user stories, 6 success criteria) + requirements checklist. Clarified at author
      time: all six components in scope; `platform` owns service lifecycle (up/down in
      dependency order).
- [ ] `/speckit.clarify` + review — optional deeper pass (the 2 critical scope decisions
      were already resolved during specify; open for plan: FR-009 coherence mechanism,
      DGX-side process scope).
- [ ] `/speckit.plan` — review boundary / render-vs-import decisions.
- [ ] `/speckit.tasks` → `/speckit.implement` — gated task by task (this edits the
      *other* repos; that cross-repo editing is the actual re-architecture).

## Context

~6 components in separate repos that work today through operational discipline,
not architecture:

- `src/dgx` — SRE toolkit + `dgxlib` (per-model request config, `models.yaml`)
- `src/mempalace` — local-first memory library (ChromaDB / optional turbovec backend)
- `src/turbovecdb` + `src/turbovecdb-service` — vector DB + thin HTTP service
- `src/CampaignGenerator` — post-session toolkit (Claude API, FastAPI+Vue)
- `src/mytools` (rpg-lib, flexai-social) — content/RPG tools
- `campaigns/gm-assistant` — markdown GM skills over the campaign workspace

Each component is individually fine. **All the pain is in the integration /
distribution / orchestration plane**: which venv, what install order, what
version, what config, what endpoint. In your own doctrine's terms this is
**Fragmented State** (config/state scattered, hand-synced) + **Infrastructure
Proxy** (infra identity hardcoded into component code), not bad internals.

Goal: turn this into a carefully architected, installable, upgradeable system,
using Spec Kit as the SDD harness for the integration plane.

## Diagnosis (grounded)

**Coupling points** (how the repos actually touch):

| From | To | Mechanism | File |
| --- | --- | --- | --- |
| CampaignGenerator | dgxlib | `import dgxlib` (editable install) | `CampaignGenerator/campaignlib/api/backends.py` |
| CampaignGenerator | mempalace | MCP wrapper + `from mempalace.searcher` | `CampaignGenerator/mempalace_client.py`, `mcp_server.py` |
| CampaignGenerator | rpg-lib | `sys.path.insert(...)` then import | `CampaignGenerator/query_rpg_lib.py` |
| mempalace | turbovecdb | entry-point plugin `mempalace.backends` | `mempalace/pyproject.toml` |
| gm-assistant | CampaignGenerator | reads the campaign workspace layout | `campaigns/gm-assistant/skills/*` |

**Concrete sources of install/upgrade/setup pain:**

1. **Hardcoded infrastructure identity** (the thing to kill first):
   - DGX endpoint `http://192.0.2.10:8001/v1` — `CampaignGenerator/extract_facts.py` (`DEFAULT_ENDPOINT`), `prep.py`, `backends.py` fallback model.
   - 5etools data root `~/src/5etools-kostadis/data` — `CampaignGenerator/config/config.yaml`.
   - rpg-lib URL `http://localhost:8000` + dir `~/src/mytools/rpg-lib` — `config/config.yaml`, `query_rpg_lib.py`.
   - turbovecdb-service port `8077`, **must** run from `~/.venvs/main`.
2. **No system-level config.** Per-tool config fragments instead: CampaignGenerator `config.yaml`, mempalace `mempalace.yaml`, dgx `models.yaml`, plus env vars (`DGX_*`, `MEMPALACE_*`). No single answer to "where is the DGX / mempalace / 5etools / which venv."
3. **No cross-component version pinning.** dgxlib/turbovecdb are editable installs — a `git checkout` in one repo silently changes another's behavior. PyPI deps unpinned (`turbovecdb>=0.1`, etc.).
4. **Implicit venv + startup order.** `~/.venvs/main` assumed but unenforced; rpg-lib server, DGX endpoint, mempalace MCP, turbovecdb-service must be up in an undocumented order. "Is it running?" is answered by `current-setup.md` discipline, not a tool.

## Does Spec Kit fit? (honest)

**What it is:** a single-project, spec-driven-development harness — `constitution
→ specify → plan → tasks → implement`, features numbered `001/002` under one
`.specify/` per repo. You already use it well in `mytools/notetaker` (5 features).

**What it is NOT:** a cross-repo packaging, dependency, or orchestration tool. It
will **not produce** your installer, lockfile, or unified config. Those are your
architecture work.

**Where it genuinely helps here:**
- A **constitution** = the right place to encode cross-repo principles once and
  hold every later change against them.
- The **workflow** gives you reviewable, incremental specs instead of a big-bang
  rewrite — the re-architecture becomes `001-…`, `002-…`, each gated.

**The doctrine guardrail (your own rule):** boundaries, dependency direction, and
the config schema are *precision decisions*. You author them (constitution + the
spec body). Spec Kit's LLM steps (`/plan`, `/implement`) **render inside** that
structure — they must not *decide* it. Good pattern: you impose structure → LLM
implements within it. Bad pattern: `/specify → /plan → /implement` deciding the
architecture unreviewed.

## Recommended target architecture

A new umbrella repo `~/src/platform` that owns the **integration plane** only.

**1. Single source of truth: `platform.yaml`** (lives in `~/src/platform`, the
one file you hand-edit). Sketch:

```yaml
venv: ~/.venvs/main
machines:
  dgx:
    endpoint: http://192.0.2.10:8001/v1
    default_model: Qwen/Qwen3-Next-80B-A3B-Instruct-FP8
data_roots:
  fivetools: ~/src/5etools-kostadis/data
  campaigns: ~/campaigns
services:
  rpg_lib:    { url: http://localhost:8000, dir: ~/src/mytools/rpg-lib }
  turbovecdb: { url: http://127.0.0.1:8077, port: 8077 }
  mempalace:  { backend: chromadb, embedding_device: cpu }
components:               # version pins -> kills editable-install drift
  dgxlib:        { source: ~/src/dgx,            pin: <git-sha-or-tag> }
  mempalace:     { source: pypi,                 pin: 3.3.5 }
  turbovecdb:    { source: pypi,                 pin: <ver> }
  CampaignGenerator: { source: ~/src/CampaignGenerator, pin: <git-sha> }
```

**2. An installer (`platform install`)** that:
- creates/validates the venv,
- installs components in dependency order at their pinned versions,
- **renders each component's native config/env from `platform.yaml`** rather than
  forcing a new shared import. (Lower coupling: components keep reading their own
  `config.yaml`/env; the installer is the only thing that knows the global truth.
  This respects boundaries and matches "human owns structure, tool renders.")

**3. Status (`platform status`)** that reports installed versions + health-checks
each service — generated, replacing the `current-setup.md` discipline.

This directly attacks pains 1–4: hardcoded constants come from one file; one
config; pinned versions; reproducible install + a real "is it up?" answer.

## How Spec Kit drives it (execution path)

In `~/src/platform`:

1. `git init && specify init` (Claude Code integration) → `.specify/`, slash
   commands. **DONE** (scaffold at repo root).
2. **`/speckit.constitution`** — **DONE 2026-06-24.** Authored directly from the
   Kostadis Engine lenses into 8 principles (`.specify/memory/constitution.md`,
   v1.0.0). Covers single source of truth, no hardcoded infra, acyclic deps,
   reproducible install, honest-status-by-tool, single-authority/no-stale-copies (V),
   human-owns-structure, and the four doctrine anti-patterns by name.
3. **`/speckit.specify 001-reproducible-install`** — spec body = the `platform.yaml`
   schema, installer responsibilities, config-rendering targets (enumerate the
   hardcoded constants above as the things to externalize), version-pinning rules.
   Run **`/speckit.clarify`** and review — this is the precision checkpoint.
   Carry the **scope boundary** below into the spec verbatim.
4. **`/speckit.plan`** — LLM drafts the technical plan; you review the boundary
   decisions (which component reads what, render-vs-import).
5. **`/speckit.tasks` → `/speckit.implement`** — builds `platform.yaml`, the
   installer/status tool, and the per-component config templates. Note: implement
   will edit the *other* repos (replace hardcoded constants with config-sourced
   values). That cross-repo editing is the actual re-architecture — gate it task
   by task.

### `001` scope boundary — the config entity, not the data plane (carry into the spec)

Principle V applies to *every* entity, but `001`'s single authority — `platform.yaml`
— owns exactly **one** of them: the **config / wiring entity** (endpoints, ports,
paths, venv, version pins). The "collapse component-local databases into
`platform.yaml`" decision means *config* state only. It does **not** mean pulling
runtime/data-plane stores into `platform.yaml`:

- **In scope for `001` (config entity → authority = `platform.yaml`):** the hardcoded
  constants (DGX endpoint, 5etools data root, rpg-lib URL/dir, turbovecdb port, venv),
  version pins, install order, and any *config* a component today hand-maintains in a
  parallel file — those get collapsed/rendered from the one authority.
- **Out of scope for `001` (separate data-plane entities, each already single-authority):**
  mempalace's ChromaDB vectors, turbovecdb's stored vectors, campaign/5etools data
  roots. These are *data*, not config. Each is its own entity that already owns its
  own truth; the fix there is **not** "move into `platform.yaml`" but "don't let a
  second store cache or duplicate it." `platform.yaml` *references* where they live
  (a path/endpoint — config) without *containing* their contents.
- **The test that keeps the boundary honest:** if a field's value is something you'd
  *edit to wire the system*, it's config → `platform.yaml`. If it's something the
  system *produces or ingests at runtime*, it's data → stays in its own store, merely
  pointed at. Principle V is satisfied for data-plane entities by each having one
  authoritative store, not by centralizing them.

**Future (hybrid):** once `platform` exists, add per-repo `.specify/` to individual
components as you rework them; Spec Kit's `SPECIFY_INIT_DIR` / `SPECIFY_FEATURE_DIRECTORY`
env vars let you operate them from the umbrella.

**Spec Kit limits to keep in mind:** it won't choose your pins, write the
dependency DAG, or run services — those are inputs you provide, not outputs it
generates.

## Verification (the acid test for `001`)

When executed, the spec is "done" when:
1. `platform install` from a single edited `platform.yaml` brings the system up on
   a fresh venv (or a second machine) with no manual path/IP edits.
2. `platform status` reports each component's pinned version + a health check per service.
3. Grep proves the constants moved: `grep -rn "192.0.2.10\|5etools-kostadis/data\|localhost:8000\|.venvs/main" src/CampaignGenerator src/dgx` returns only config/template references, not logic.
4. Change the DGX IP in `platform.yaml` only, re-render, and every component picks it up.

## Decisions captured

- Apply Spec Kit via an **umbrella `~/src/platform` project**.
- **First spec = reproducible install + unified config** (pains 1–4 above).
- Component repos untouched until `001` is executed and reviewed.
- Scaffold stood up 2026-06-24 (`git init` + `specify init`), un-nested to repo
  root same day; constitution authored 2026-06-24; `001` spec still to author.
- **Single-authority is non-negotiable, breaking changes accepted (2026-06-24):**
  today's state spread across multiple hand-maintained config files + databases is
  the bug, not a constraint. Constitution Principle V wins over VII (low coupling):
  components will be forced to change — collapse component-local DBs into
  `platform.yaml`, replace hand-edited configs with generated ones — to reach one
  authority. The sin is multiple *authorities*, not multiple physical files; derived
  read-only copies kept coherent with the one authority are fine.
