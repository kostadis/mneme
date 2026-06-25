# 0004 — gm-assistant skills reference `~/src/campaigns` but live in `~/campaigns`

**Status:** open (2026-06-24)
**Area:** gm-assistant (campaigns repo) · workspace paths · T021
**Related:** `~/campaigns/gm-assistant/{SKILLS.md,README.md,skills/*/SKILL.md}`, mneme `data_roots.campaigns`

## Problem

gm-assistant's docs and skills reference the campaign workspace as **`~/src/campaigns/`**, e.g.:
- `SKILLS.md`: "Canonical files live at `~/src/campaigns/gm-assistant/skills/gm-*/SKILL.md`. Runtime
  symlinks at `~/src/campaigns/.claude/skills/gm-*` …"
- "refuse to operate outside one of the campaign subdirs … see `~/src/campaigns/CLAUDE.md`"
- `README.md`: `git clone <campaigns repo url> ~/src/campaigns`, the `.claude/skills` symlink checks, etc.

But gm-assistant actually lives in **`~/campaigns/`** (the campaigns git repo — `git rev-parse
--show-toplevel` → `/home/kroussos/campaigns`). And **both directories exist**: `~/src/campaigns`
is a *separate* dir (just an `Obelisk/` tree, not the campaigns repo). So the skills point GMs /
Claude Code at the **wrong workspace root** — the symlink instructions, campaign-isolation rule,
and `CLAUDE.md` references resolve to the wrong (or empty) location.

mneme's authority already uses the correct path: `data_roots.campaigns: ~/campaigns`.

## Fix

Replace `~/src/campaigns` → `~/campaigns` throughout gm-assistant (SKILLS.md, README.md, and the
`skills/*/SKILL.md` files), OR decide which is canonical and align everything (incl. the actual
symlink locations). Pure docs/markdown change in the campaigns repo — no mneme code involved.
