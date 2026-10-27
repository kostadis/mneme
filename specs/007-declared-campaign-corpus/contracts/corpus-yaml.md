# Contract: `.mneme/corpus.yaml` (authority, tracked)

The one place a campaign declares its corpus (FR-001, FR-001a). It is hand-edited by the
GM. mneme reads it and never writes it, except that `mneme corpus init` creates a skeleton
with no paths when the file is absent.

## Shape

```yaml
campaign: toee

kinds:                       # standard kinds only (recipe `kinds:`: v3 five, v4 adds `arcs`)
  npcs:
    dirs: [docs/npcs]
  summaries:
    dirs: [docs/summaries]
  grounding:
    files:
      - docs/world_state.md
      - docs/campaign_state.md
      - docs/party.md
      - docs/planning.md
  party:
    dirs: [docs/party]
    files:
      - docs/party.md
    mined_as: true           # docs/party.md is in grounding too; mine it as party (R2)
  prep:
    dirs: [notes/sessions]
    trust: reference         # optional override of the standard default

campaign_kinds:              # campaign-defined kinds (FR-003a)
  backstories:
    files: [docs/daz_backstory.md, docs/gyrgum_backstory.md]
    trust: reference         # required: there is no default for a campaign kind
```

## Rules

- Paths are relative to the campaign root, use POSIX separators, and are normalized. They
  must not be absolute and must not contain `..`.
- `dirs` entries admit everything below them, recursively. `files` entries name exact files.
- An omitted kind is **not declared** for this campaign. That is distinct from a declared
  kind that resolves to no files, which the TOC records as `declared: true, files: []`.
- `mined_as` applies to the files *that declaration* names which are also reachable from
  another kind. Exactly one of the overlapping declarations may set it.
- A gitignored path you name (a `files` entry, a `dirs` entry, or a symlink's target) is an
  error. A gitignored file merely found inside a `dirs` entry is left out of the corpus, with
  no finding (mneme#64).
- Unknown top-level keys and unknown per-kind keys are errors. A misspelled key must not
  disappear silently.
- Validation is in `data-model.md` § Validation rules. Every violation is a status finding
  naming the path and the rule. None is auto-corrected.

## Relationship to `.mneme/mempalace.yaml`

When this file exists, the mempalace authority keeps `campaign`, `recipe_version`, `store`
and `dispositions` only. `wings:` and `extra_exclusions:` there are `invalid: dual-authority`.
The wings are derived from the kinds declared here (research R8).
