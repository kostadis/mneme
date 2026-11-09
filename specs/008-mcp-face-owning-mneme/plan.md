# Implementation Plan: MCP Face Bound to the Owning mneme

**Branch**: `008-mcp-face-owning-mneme` | **Date**: 2026-11-09 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/008-mcp-face-owning-mneme/spec.md` (GH kostadis/mneme#87)

## Summary

The mcp face (`render_mcp`) today writes one `mempalace` server, by bare program name, into the
campaign's `.mcp.json`, and never registers mneme's own advisory server. This feature:

1. writes a `mneme` server entry (`<venv>/bin/mneme mp mcp --config <hypostasis.yaml>`) and pins
   the `mempalace` entry to `<venv>/bin/mempalace-mcp`, both taken from the **owning** mneme's
   loaded config, and only for campaigns that mneme owns;
2. also writes both entries at the **clone root** (`ref.tree`, e.g. `~/toee`) when that sparse
   clone holds exactly one campaign. Campaigns are counted against a host-declared
   `campaign_shared_dirs` list in hypostasis.yaml. Several campaigns → to-do. Several campaigns
   plus existing root entries → FAIL, and nothing is written;
3. extends `faces_coherent` and adds a `clone` status row so a missing, foreign or bare entry
   and a bad clone layout all appear in `mp status`.

Repair command: `mneme mp faces <campaign>` (refresh stays mining-only — research R5).

## Technical Context

**Language/Version**: Python 3.12 (existing `mneme` + `hypostasis` packages, same repo)

**Primary Dependencies**: typer (CLI), PyYAML; no new dependencies

**Storage**: host-local JSON files (`.mcp.json`), hypostasis.yaml (one new optional key)

**Testing**: pytest (`tests/unit`), ruff

**Target Platform**: Linux host running one or more mnemes

**Project Type**: CLI + library (`mneme mp …`, `hypostasis`)

**Performance Goals**: n/a. One directory listing and two small JSON reads per campaign per status run

**Constraints**: never resolve programs through PATH; never write a clone root in a non-`SINGLE`
verdict; atomic writes; no secrets in `.mcp.json`

**Scale/Scope**: ~5 campaigns per host; changes in `render.py`, `conform.py`, `bringup.py`,
`models.py` (State), `cli.py` (`faces` output), `hypostasis/config.py` + `models.py`

## Constitution Check

| Principle | Assessment |
|---|---|
| I. Silicon Truth | Status reads the files actually on disk and checks that the programs exist. An undeclared shared set gives a to-do, not a guessed count (data-model verdict ordering). ✅ |
| II. Sovereign Identity | Program and config paths come from `ConfigEntity.venv` / `source_path` (injected config), never hardcoded and never from PATH. ✅ |
| III. Intrinsic State | No new side store. The face is derived from authority + hypostasis config every time. ✅ |
| IV. Transient Viewer | The MCP entries are rendered config. Deleting them loses nothing that `mp faces` can't rebuild. ✅ |
| V. One Entity, One DB | hypostasis.yaml stays the one authority. `campaign_shared_dirs` lives there (GM decision), not duplicated per campaign. ✅ |
| VI. Federated Authority | Ownership gate: a mneme only writes campaigns it OWNS, so two mnemes on one host never write each other's campaigns. ✅ |
| IX. Observability | New reasons in the `faces` row plus a new `clone` row. The toee gap ("right store everywhere" while no server existed) becomes visible. ✅ |
| Human checkpoint | The shared-set contents on this host are the GM's (quickstart §3). The FAIL on a misconfigured clone changes nothing; the GM resolves it. ✅ |

Post-design re-check: still ✅. No violations, so Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/008-mcp-face-owning-mneme/
├── spec.md
├── plan.md              # this file
├── research.md          # R1–R9
├── data-model.md        # McpBinding, CloneLayout verdicts, hypostasis key, rows
├── quickstart.md        # gates, scenario table, live check
├── contracts/
│   ├── mcp-face.md      # entries, write rules, who renders
│   └── status-rows.md   # faces reasons, clone row
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
hypostasis/
├── models.py            # ConfigEntity.campaign_shared_dirs: tuple[str, ...] | None
└── config.py            # parse + validate campaign_shared_dirs

mneme/mempalace/
├── mcpface.py           # NEW: McpBinding (from entity), CloneLayout + verdict, atomic merge-write,
│                        #      entry builders, per-file coherence reasons
├── render.py            # render_mcp/render_faces delegate to mcpface; mneme entry without store;
│                        #      faces_coherent gains binding + clone-root checks
├── bringup.py           # pass entity/ref to render_faces; ownership gate in render_existing_faces
├── conform.py           # faces row uses new reasons; new `clone` row
├── models.py            # State.CLONE_ROOT_OWED, State.CLONE_ROOT_CONFLICT (+ FAIL_STATES)
└── cli.py               # `mp faces` prints rendered/skipped root line

tests/unit/
├── test_mcpface.py      # NEW: binding, verdicts, merge-write, coherence reasons
├── test_render.py       # updated render_mcp expectations
├── test_mp_conform.py   # faces reasons + clone row
└── test_hypostasis_config*.py  # campaign_shared_dirs parse/validate (name per existing file)
```

**Structure Decision**: new logic goes in one new module, `mcpface.py`, so `render.py` stays a
thin caller. The existing tests that pin today's `render_mcp` output (bare `mempalace-mcp`) are
updated, since the behaviour change is intended (US2).

## Dependencies

- No cross-repo work. mempalace and campaigns are untouched (campaigns#672 is separate).
- Phase order: hypostasis key → `mcpface.py` → render/bringup wiring → status → CLI output.

## Execution Model

Decided by the GM on 2026-11-09. It binds `/speckit-tasks` and `/speckit-implement` for this
feature.

- **Worktree and branch**: all work happens in `~/src/mneme-008` on branch
  `008-mcp-face-owning-mneme`, never in the `~/src/mneme` checkout on `main`.
- **Orchestrator: Opus** (the main session). It owns task sequencing, every precision decision,
  writing each implementation brief, and verifying each result against `tasks.md` and the
  contracts. It does not delegate scope, ordering or attribution decisions.
- **Implementers: Sonnet** (`model: sonnet`, `effort: medium`) subagents, one per task or tightly
  coupled task group. Each brief carries the task, the files it may touch, the contract sections
  it must satisfy and the tests that prove it. Groups with no shared files may run in parallel.
- **Gate after each phase**: Opus runs `ruff check .` and `pytest -q tests/unit` itself and reads
  the diff before the next phase. A failing gate goes back to an implementer with the failure.
  Never run pytest under `git rebase --exec` (tests inherit `GIT_DIR`).
- **Exactly one code-review pass**: after the last implementation phase and before the PR, Opus
  runs `/code-review` once on the branch diff. Findings that are cheap and clearly in scope are
  fixed by an implementer and re-gated. There is **no second review pass**.
- **Leftovers become issues**: every review finding not fixed, and every follow-up this plan
  already knows about, is filed as a GitHub issue (kostadis/mneme via the GitHub MCP tools) after
  the PR is opened and linked from the PR. Known follow-ups:
  - discovery should use `campaign_shared_dirs` to stop reporting `gm-assistant`/`scripts` as
    campaigns (research R4);
  - the other campaign-side servers (`campaign`, `5etools`, `registry`, `provenance`) are also
    resolved through PATH (spec Assumptions; owner TBD, likely CampaignGenerator).
- **Human checkpoints stay human**: the `campaign_shared_dirs` value in this host's
  hypostasis.yaml and running `mp faces` against the live campaigns (quickstart §3–4) belong to
  the GM. No subagent edits `~/.config/hypostasis/hypostasis.yaml` or touches `~/toee` etc.

## Complexity Tracking

None.
