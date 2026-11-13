# Specification Quality Checklist: Corpus Brief

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-11-13
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- The spec names the user-facing surfaces (`mneme corpus brief`, `--json`, the `corpus_brief`
  tool, the `brief:` key). These are the user's stated interface, and mneme's earlier specs
  (007, 008) name their surfaces the same way. No module, data structure or library is named.
- No clarification markers: the open design choices were settled by the GM in session
  (2026-11-13): a top-level `brief:` list; hard refusal for campaigns with no corpus; spec
  lives in mneme and covers the API and the consumer contract, with skill migration left to
  mytools#87.
- Revised 2026-11-13 after the GM reframed the corpus: planning is the corpus's product and is
  what gets loaded; grounding and evidence are searched. The brief stays a generic `brief:` list
  (GM decision); the map now says which kinds are searchable. The checklist re-validated clean.
  The Input line keeps the original description verbatim, including its "345 KB" figure.
- Scope addition 2026-11-13 (GM request): `migrate-brief` (User Story 5, FR-016–FR-020); FR-004
  narrowed so mneme writes `brief:` only through that GM-run, preview-first command.
  Re-validated clean.
