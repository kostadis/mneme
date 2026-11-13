# Data Model: Corpus Brief (009)

Extends 007's model (`specs/007-declared-campaign-corpus/data-model.md`). Nothing here is
stored by mneme: the brief is part of `corpus.yaml` (GM-authored, tracked), and the brief
answer is derived per request.

## Brief (declaration)

Part of `CorpusConfig`.

| Field | Type | Rule |
|---|---|---|
| `brief` | ordered tuple of campaign-relative POSIX paths | Optional. Absent ⇒ `()`. |

Validation (structural, in `config.py`; every violation is a finding, all reported at once):

| Code | When |
|---|---|
| `malformed` | `brief:` is not a list of strings; an entry is listed twice |
| `path-escape` | an entry is absolute, escapes the root, uses `\`, names the root, or is empty |
| `empty-declaration` | `brief: []` |

Validation (membership, in `resolve.py`):

| Code | When |
|---|---|
| `brief-undeclared` | an entry is not a resolved file of any kind and not a declared-but-absent (`not_materialized` / `missing`) path of any kind. This covers folders, gitignored files and undeclared files. |

Any finding makes the corpus invalid (007 rule), so every 007 reader refuses as well.

## Brief answer (derived, never stored)

Produced by `api.brief(campaign_dir, recipe)` from one fresh resolution. Schema in
`contracts/brief-json.md`.

| Field | Meaning |
|---|---|
| `schema` | `1` |
| `campaign` | from `corpus.yaml` |
| `corpus_sha256` | sha256 of the exact `corpus.yaml` bytes this answer was resolved from |
| `brief[]` | in declared order: `path`, `kinds` (every kind the file resolves under, declaration order), `trust`, `bytes` |
| `brief_bytes` | sum of `brief[].bytes` |
| `kinds{}` | per declared kind: `standard`, `trust`, `files`, `bytes`, `searchable`, `searchable_files` |

Derivation rules:

- A brief file's `trust` is its kinds' trust. 007 rule 6 already makes a file shared by
  kinds with different trust a `trust-conflict` finding, so the value is single.
- `kinds{}.searchable_files` counts resolved files with `minable: true` and non-null
  `mined_as`; `searchable` is `searchable_files > 0` (research R4).
- `bytes` is measured at answer time on the declared path (research R6).

## Answer states

```text
corpus.yaml absent ───────────────▶ refuse not-declared
corpus invalid (any finding) ──────▶ refuse invalid (findings)
valid, brief == () ────────────────▶ refuse no-brief
valid, some brief entry not on disk ▶ refuse brief-unavailable (names each)
valid, all brief files present ────▶ answer
```

Discovery failures (unknown campaign, foreign owner, store-alias clash) occur before this
diagram and propagate as they do for `corpus toc`.

## Consumer (inventory row, `consumers.yaml`)

| Field | Change |
|---|---|
| `mode` | gains `brief` (compliant). `MODES = (palace, toc, brief, partial, independent)`. |

## Brief migration (per campaign, not stored)

| Step | Outcome |
|---|---|
| resolve campaign (name / `--dir` / `--all`) | discovery errors refuse that campaign |
| no `corpus.yaml` | refuse `not-declared` |
| corpus invalid | refuse `invalid` (findings) |
| `brief` key already present | refuse `brief-exists` |
| a `--file` not a declared, present corpus file | refuse `brief-undeclared` / `brief-unavailable` (names it) |
| new bytes fail validation | refuse `invalid` (never written) |
| preview (default) | print block + per-file kinds/bytes + total; write nothing |
| `--apply` | atomic replace with original bytes + appended block |
