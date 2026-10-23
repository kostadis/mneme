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

## Declared corpus (`.mneme/corpus.yaml`)

A campaign may declare exactly which files are its corpus, instead of the wing model. When
`.mneme/corpus.yaml` exists, it is the single source of truth: the palace, status and every
other reader derive from it. mneme reads it and never writes membership; only the GM edits it.

```yaml
campaign: toee
kinds:                       # standard kinds: npcs, summaries, party, grounding, prep
  npcs:
    dirs: [docs/npcs]        # a dir admits everything below it, recursively
  grounding:
    files: [docs/world_state.md, docs/party.md]   # exact files
  party:
    files: [docs/party.md]
    mined_as: true           # shared with grounding: mine its drawers as `party`
  prep:
    dirs: [notes/sessions]
    trust: reference         # optional override of the kind's default trust
campaign_kinds:              # campaign-defined kinds
  backstories:
    files: [docs/daz_backstory.md]
    trust: reference         # required: a campaign kind has no default
```

- A kind that is omitted is **not declared**. That is distinct from a declared kind that
  resolves to no files (`files: []`).
- `trust` is `authoritative`, `accelerator` or `reference`; standard kinds have a default.
- `mined_as: true` on one declaration says a file reachable from two kinds is mined as that
  kind. Exactly one of the overlapping declarations may set it.
- Unknown keys, gitignored paths, absolute or `..` paths and conflicting declarations are
  errors, never auto-corrected.
- **Symlinks.** A declared path may be a symlink whose target is a regular file inside the
  campaign. mneme mines the resolved target; consumers still open the declared `path`. A
  symlink that resolves outside the campaign, or to a non-file, is invalid.

### Consumer obligations

Anything that reads campaign files MUST get the list from mneme, on every use:

1. `mneme corpus toc CAMPAIGN --kind K --json`, or the `corpus_files(campaign, kind)` tool of
   this server. Both resolve `corpus.yaml` against the disk on every call, so a file added to
   a declared folder appears without a render.
2. If mneme exits non-zero, returns an `error` (`invalid` or `not-declared`), or reports
   `valid: false`, **refuse** and print what mneme said. Never fall back to globbing.
3. Take the files from `kinds.<kind>.files[].path` and nothing else. A kind that is not
   declared is "not declared for this campaign", not an empty list.

Never read `.mneme/corpus.toc.json` and never glob. That file is a host-local snapshot for
inspection and for status's `toc-stale` check; it can be stale or hand-edited.

### Remedies

| Status says | Fix |
|---|---|
| `undeclared-drawers` (palace holds files the corpus does not) | `mneme mp prune CAMPAIGN` (preview, then `--confirm --expect N`; former canon wings also need `--include-former-canon WING`) |
| `missing` (a declared path is gone, not merely outside this sparse checkout) | fix or remove the path in `.mneme/corpus.yaml`; `mneme mp prune` drops its drawers |
| `unmined`, `stale` or `wrong-wing` (declared files not yet mined, changed, re-pointed, or mined under another kind) | `mneme mp refresh CAMPAIGN` |
| `toc-stale` (snapshot differs from a fresh resolution) | `mneme mp render CAMPAIGN` |
| `out-of-scope` (drawers point outside the campaign: a moved campaign or a foreign store) | `mneme mp regenerate CAMPAIGN --confirm` |
| `invalid` (the configuration or a path is wrong) | edit `.mneme/corpus.yaml`, check with `mneme corpus check CAMPAIGN` |
