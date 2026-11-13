# Contract: `brief:` in `.mneme/corpus.yaml` (delta to 007 `corpus-yaml.md`)

## Shape

```yaml
campaign: out-of-the-abyss
kinds:
  grounding:
    dirs: [docs/reference]
    files: [docs/world_state.md, docs/campaign_state.md, docs/party.md, docs/planning.md]
  # … other kinds unchanged …

brief:                      # optional; the GM's load-now set, in reading order
  - docs/planning.md
```

## Rules

- `brief:` is an optional top-level key: a non-empty list of exact file paths. It allows no
  folders, no patterns, and no duplicates.
- Paths follow 007's path rules: relative, POSIX, normalized, never escaping the root.
- Every entry must be a file of some declared kind on this declaration. An entry that is not
  is a `brief-undeclared` finding, which makes the corpus invalid. That includes a folder, a
  gitignored file, and a file outside every kind.
- An entry declared under a kind but absent on this checkout (not materialized or missing)
  is **not** a finding; the brief answer refuses it instead (`brief-unavailable`).
- mneme writes `brief:` only through `mneme corpus migrate-brief --apply`, and only by
  appending a previewed block to a file that has none. Every other mneme edit of
  `corpus.yaml` leaves it byte-for-byte unchanged.
- `mneme corpus init`'s skeleton shows it as a comment, with no active entry.
