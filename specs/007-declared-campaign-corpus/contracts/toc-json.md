# Contract: `.mneme/corpus.toc.json` (derived TOC, host-local)

What every consumer of campaign files reads (FR-021). It is written by `mneme mp render`,
`mp refresh` and `mneme corpus toc --write`, and appended to the campaign's `.gitignore`.
It must never be hand-edited. A hand-edited TOC fails the freshness check below and is
regenerated.

## Shape (schema 1)

```json
{
  "schema": 1,
  "generated_by": "mneme <version>",
  "campaign": "toee",
  "corpus_sha256": "<sha256 of the exact bytes of .mneme/corpus.yaml>",
  "recipe_version": "3.0.0",
  "valid": true,
  "findings": [],
  "kinds": {
    "grounding": {
      "standard": true,
      "trust": "authoritative",
      "files": [
        {"path": "docs/world_state.md", "target": "docs/grounding/generations/g72/live/world_state.md", "sha256": "…", "minable": true, "mined_as": "grounding"},
        {"path": "docs/party.md",       "sha256": "…", "minable": true, "mined_as": "party"}
      ],
      "not_materialized": [],
      "missing": []
    },
    "summaries": {"standard": true, "trust": "authoritative", "files": [], "not_materialized": [], "missing": []}
  }
}
```

- A kind **absent** from `kinds` is not declared for this campaign. `files: []` means it is
  declared and empty (FR-013).
- `files` is sorted by `path`. `path` is campaign-relative and POSIX: it is the declared path,
  which consumers open. `target` is present only when `path` is a symlink; it is the resolved
  campaign-relative file that was hashed and mined. `sha256` is of the target's bytes.
- `mined_as` names the wing (kind) that holds the file's drawers (R2). It equals the
  enclosing kind unless the file is shared across kinds.
- `valid: false` with a non-empty `findings` list means the configuration is invalid. Each
  finding is `{code, path?, detail}`.

## Consumer obligations (FR-021, FR-022)

A consumer that reads campaign files directly MUST, before acting:

1. Read `.mneme/corpus.toc.json`. If it is missing → refuse: "no corpus TOC — run
   `mneme mp render <campaign>`".
2. Hash `.mneme/corpus.yaml` and compare with `corpus_sha256`. If they differ → refuse: "TOC
   stale".
3. If `valid` is false → refuse and print `findings`.
4. Take the files for each kind it needs from `kinds.<kind>.files[].path`, and nothing else.
   No globbing, probing or hardcoded paths for corpus material.
5. Optionally compare each file's sha256 to detect an edit since resolution, and refuse or
   warn as that consumer's own contract specifies.

A consumer asking for a kind that is not declared gets a distinct answer ("not declared for
this campaign"), not an empty list.

Convenience readers that apply 1–3 for you: `mneme corpus toc CAMPAIGN [--kind K] --json`,
and the `corpus_files(campaign, kind)` tool in `mneme mp mcp`.
