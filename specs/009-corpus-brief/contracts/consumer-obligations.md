# Contract: consumer obligations (delta to `mneme/recipes/instructions/manage-mempalace.md`)

Text to add to § Consumer obligations, after rule 3:

> 4. A **briefing consumer** (one that loads a campaign's context up front, such as
>    `campaign-prep`) calls `mneme corpus brief CAMPAIGN --json` or the `corpus_brief` tool,
>    reads the files in `brief[].path` and nothing else at load time, and keeps `kinds` as its
>    map. Everything else, grounding documents included, is reached by searching the palace;
>    a claim is confirmed by reading the cited source. A per-kind file list is still
>    `corpus toc --kind K` / `corpus_files`.
> 5. On any `error` (`not-declared`, `invalid`, `no-brief`, `brief-unavailable`) the consumer
>    refuses and shows mneme's `detail` to the GM. A missing brief is never replaced by a whole
>    kind, a remembered list, or the map alone. The fix for `no-brief` is
>    `mneme corpus migrate-brief CAMPAIGN` (preview), then `--apply`.

`consumers.yaml`: a briefing consumer's row is `mode: brief`, compliant. `kinds:` lists the
kinds its brief files come from.
