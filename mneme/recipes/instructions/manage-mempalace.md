# Managing a Campaign Mempalace (mneme-owned method)

This is the mneme-owned, versioned procedural method for building, configuring, and
migrating a campaign's mempalace — served on demand by `mneme mp mcp` so an assistant
loads it instead of the human pasting docs (FR-028/029). It is the prose counterpart
to the machine recipe (`mneme/recipes/mempalace.recipe.v1.yaml`); the campaigns repo's
`MEMPALACE_HOWTO.md` is the same method's narrative rationale.

## Core model

- **One authority per campaign** lives in the campaign at `.mneme/mempalace.yaml`:
  its wings (each with a `source` dir, `trust` level, and `rooms`), `extra_exclusions`,
  the adopted `recipe_version`, and recorded `dispositions`. This is the only file you
  edit. The per-wing `mempalace.yaml` and `.mempalaceignore` are **rendered** from it
  and stamped do-not-edit — never hand-edit them.
- **mneme facilitates; the campaign decides.** What content a campaign indexes is the
  campaign's choice. The recipe's mechanical layer is enforced; the wing **scaffold**
  is a recommendation you may override (record a `deliberate` disposition with a reason).

## When designing or migrating a campaign's structure

The structure must serve *this* campaign's needs — reason it out; do not apply a fixed
template. Use the recipe scaffold as a starting point:

- **three-wing** (CampaignGenerator pipeline): `narrative` (chapter splits of the bible,
  *authoritative*), `chronicle` (extraction dir, *accelerator*), `<campaign>` (reference
  docs, *reference*). Share `npcs`/`world` room names across wings to create tunnels.
- **two-wing** (no pipeline): `narrative` + `<campaign>`.
- **single-wing** (no pipeline at all): `<campaign>`.

Steps that commonly appear in a migration plan (all **content-preserving** — never
rewrite prose):

1. **split** an oversized bible (> ~2000 lines) into `docs/chapters/chapter_NN.md` on
   `# Chapter` headings — verbatim; the chapters must concatenate back to the source.
2. **move/rename** files into their wing's `source` dir.
3. **write_authority** — emit the new `.mneme/mempalace.yaml`.
4. **reindex** — note which wings to re-mine (the actual mine runs on `mneme mp refresh`).

## Hard rules (enforced regardless of the plan)

- **Verbatim**: migration may move/split/rename/re-index, never rewrite document
  content. A content-rewriting step is refused.
- **Write isolation**: changes are staged in mneme's private working copy and adopted
  per campaign through version control — never edited into the active checkout.
- **Verify**: after a migration, mneme confirms the *actual* resulting index/config
  conforms; an incomplete migration is never reported healthy.
- **Exclusions**: keep `summaries/`, `logs/`, `voice/`, `examples/`, `notes/`,
  `.claude/`, `MEMPALACE.md`, and tooling files out of the index (recipe baseline).
- **Mining order**: sub-scopes before the root, so the root `.mempalaceignore` can
  exclude wing dirs and prevent double-mining.
