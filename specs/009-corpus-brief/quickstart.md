# Quickstart: Corpus Brief (009) validation

Each scenario proves one story. Automated versions run against the 007 fixture campaign
(`tests/fixtures/corpus_campaign.py`, `corpus_world`); the live versions run against the GM's
four campaigns and change nothing until step 6's `--apply`.

## Prerequisites

- mneme installed editable in `~/.venvs/main` (`mneme --help` shows `corpus brief` and
  `corpus migrate-brief`).
- Run from the workspace mneme owns (e.g. `cd ~/out-of-the-abyss/out-of-the-abyss`).

## 1. No brief yet → consumers refuse (Story 3)

```bash
mneme corpus brief out-of-the-abyss            # exit ≠ 0: error: corpus.yaml declares no `brief:` …
mneme corpus check out-of-the-abyss | tail -2  # brief: not declared / corpus is valid
```

## 2. Migration preview writes nothing (Story 5)

```bash
git -C ~/out-of-the-abyss status --short out-of-the-abyss/.mneme   # clean
mneme corpus migrate-brief out-of-the-abyss                        # prints the block + docs/planning.md [grounding] 43304
git -C ~/out-of-the-abyss status --short out-of-the-abyss/.mneme   # still clean
```

## 3. Migration refusals (Story 5)

```bash
mneme corpus migrate-brief out-of-the-abyss --file docs/nope.md     # refuses: brief-undeclared, names docs/nope.md
mneme corpus migrate-brief stormgiants --dir ~/storm-giant/stormgiants   # refuses: not-declared
```

## 4. Brief answer (Story 1), after a test-only apply in the fixture

The automated test applies to the fixture, then:

- `corpus brief --json` → `brief == [{"path": "docs/planning.md", …}]`, one `kinds` entry per
  declared kind, no per-file listing, `searchable_files` matching the kind's minable files.
- MCP `corpus_brief("corp")` == the CLI JSON (SC-004).
- Add `docs/npcs/b.md` → next answer's `kinds.npcs.files` is one higher, with no render
  (SC-005).
- Answer size < 2 KB (SC-007).

## 5. Declaration errors (Story 2)

In the fixture: `brief: [docs/npcs]`, `brief: [docs/undeclared.md]`,
`brief: [docs/planning.md, docs/planning.md]`, `brief: []`, `brief: [../x.md]` → each fails
`corpus check` with the finding named in `data-model.md`. `corpus toc` refuses too (invalid).

## 6. Live migration (GM, after the feature ships)

```bash
for c in obelisk toee out-of-the-abyss Phandalin; do mneme corpus migrate-brief "$c"; done   # review
mneme corpus migrate-brief --all --apply
mneme corpus check out-of-the-abyss | tail -2   # brief: 1 file(s), 43304 bytes / corpus is valid
git -C ~/out-of-the-abyss diff                  # only the appended brief: block
```

Then commit each campaign's `corpus.yaml` in the campaigns repo.

## 7. Stale copy is refused (Story 3, scenario 5)

```bash
mneme corpus brief obelisk --dir ~/src/campaigns/obelisk   # refuses: store alias 'obelisk' is claimed by 2 campaigns
```
