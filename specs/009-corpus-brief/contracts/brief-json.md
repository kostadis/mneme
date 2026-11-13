# Contract: the brief answer (JSON, schema 1)

Returned by `mneme corpus brief CAMPAIGN --json` and, field-for-field, by the MCP tool
`corpus_brief(campaign)`. Derived on every call; never written to disk.

```json
{
  "schema": 1,
  "campaign": "out-of-the-abyss",
  "corpus_sha256": "5f0c…",
  "brief": [
    {"path": "docs/planning.md", "kinds": ["grounding"], "trust": "authoritative", "bytes": 43304}
  ],
  "brief_bytes": 43304,
  "kinds": {
    "grounding": {"standard": true, "trust": "authoritative", "files": 15, "bytes": 786245,
                  "searchable": true, "searchable_files": 15},
    "npcs":      {"standard": true, "trust": "authoritative", "files": 109, "bytes": 0,
                  "searchable": true, "searchable_files": 109}
  }
}
```

(The `npcs` byte count above is illustrative.)

| Field | Type | Meaning |
|---|---|---|
| `schema` | int | `1` |
| `campaign` | str | `corpus.yaml`'s `campaign:` |
| `corpus_sha256` | str | sha256 of the `corpus.yaml` bytes this answer was resolved from |
| `brief[]` | list | declared order; each entry: `path` (declared, campaign-relative), `kinds` (every kind it resolves under, declaration order), `trust`, `bytes` |
| `brief_bytes` | int | sum of `brief[].bytes` |
| `kinds` | object | every declared kind, declaration order: `standard`, `trust`, `files` (count), `bytes` (sum), `searchable` (bool), `searchable_files` (count of files declared to be mined, research R4) |

Guarantees:

- The answer never contains file contents and never a per-file list of the corpus outside
  `brief`.
- The answer does not query the palace. `searchable` is declared, not observed (FR-007a).
- Consumers read `brief[].path` relative to the campaign workspace and nothing else at load
  time. For anything else they search the palace or ask `corpus toc --kind K`.

## Refusal (MCP)

```json
{"campaign": "out-of-the-abyss", "error": "no-brief", "detail": "corpus.yaml declares no `brief:` …"}
```

`error` ∈ `not-declared` | `invalid` | `no-brief` | `brief-unavailable`. Discovery failures
(unknown campaign, foreign owner, store-alias clash) raise as they do for `corpus_files`.
A consumer that gets any `error` refuses and shows `detail` to the GM.
