# Specification Quality Checklist: Declared Campaign Corpus

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-23
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

- Revised 2026-10-23: the corpus is declared by kind (NPC data, summaries, party,
  grounding, prep), each kind mapped to a directory or list of files per campaign. This
  removed the prep-scope and PC-location questions — those are now per-campaign
  configuration values, not spec decisions.
- Resolved 2026-10-23: every consumer of campaign files MUST use the mneme TOC
  (renamed from "manifest"); direct readers refuse on a missing/stale/invalid TOC
  (FR-021–FR-024). No [NEEDS CLARIFICATION] markers remain.
- Resolved 2026-10-23: kinds are both mneme-defined (standard) and campaign-defined
  (FR-003, FR-003a); campaign kinds must be explicitly declared so typos are caught.
- Resolved 2026-10-23: the corpus configuration is its own YAML file (FR-001a). No open
  questions or unreviewed proposals remain.
- Domain names that appear (mempalace, `mneme mp status`, `.mneme/mempalace.yaml`,
  `.gitignore`) are the product's own user-facing surfaces, not implementation choices.
- Per the constitution, the spec body is the GM's to own; this is a draft for review.
