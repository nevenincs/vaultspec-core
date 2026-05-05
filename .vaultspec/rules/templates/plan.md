---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #index #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/plan/ location)
# Feature tag (replace {feature} with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#plan'
  - '#{feature}'
# ISO date format (e.g., 2026-02-06)
date: '{yyyy-mm-dd}'
# Complexity tier (mandatory for new plans).
# Allowed: L1 (Steps only), L2 (Phases above Steps),
# L3 (Waves above Phases above Steps), L4 (Epic above Waves
# above Phases above Steps; PM association required).
# Pre-existing plans without this field default to L2.
tier: L2
# Related documents as quoted wiki-links.
# Carries the AUTHORISING documents (ADR, research, reference,
# prior plan) for every Step in this plan; Steps inherit this
# chain; per-row reference footers do not exist.
related:
  - '[[{yyyy-mm-dd-*}]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - The related: field carries the AUTHORISING documents (ADR, research,
       reference, prior plan) for every Step in this plan. Steps inherit this
       chain; per-row reference footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution-log artefact: <Step Record>.
     Tier is declared in frontmatter as tier: L1/L2/L3/L4
     (mandatory for new plans; pre-existing plans without the
     field default to L2 and the writer adds the field on first
     edit). The tier selects containers:
       L1 = Steps only (single session; single concern; one
            cohesive change; one day or less; no cross-module
            coupling).
       L2 = Phases above Steps (1-3 days; all Steps within a single
            package, subsystem, or configuration domain; multiple
            Phases each grouping logically related Steps; no hard
            interdependencies between Phases).
       L3 = Waves above Phases above Steps (3-10 days; multi-
            session; hard interdependencies between batches; one
            batch must land before another can begin; codebase
            reordering or foundational changes; Steps span two or
            more boundaries with hard ordering between them).
       L4 = Epic above Waves above Phases above Steps (multi-week
            or multi-month; multi-team or multi-agent; tracking
            required against external project-management artefacts;
            MVP, business case, or equivalent governance; PM
            association declared in Epic intent block prose).
     Selection is by complexity criteria, not container counting.
     Writer never invents containers to qualify a tier. -->

<!-- IDENTIFIERS AND ROW CONTRACT:
     S##, P##, W## are flat, per-document, append-only, immutable.
     Promotion adds containers without renumbering. Gaps are not
     reused.
     Display paths are computed from current grouping:
       Step path:    L1 S##   L2 P##.S##   L3/L4 W##.P##.S##
       Phase heading:        L2 P##       L3/L4 W##.P##
       Wave heading:                      L3/L4 W##
     Row format:
       - [ ] `<display-path>` - imperative-verb action; `path/to/file`.
     Two-state checkboxes only ([ ] open, [x] closed). No per-row
     reference footers; wiki-links and markdown links are forbidden
     in plan body. Authorising documents go in the plan's `related:`
     frontmatter once.
     ASCII spaced hyphens everywhere; em-dash (U+2014) and en-dash
     (U+2013) are forbidden. Step rows within a Phase are
     contiguous. -->

<!-- NO COMPRESSION:
     N self-similar actions = N rows. Never collapse into "for each
     X, do Y" / "across all callers, do Z" / "in every module,
     replace W". The rule applies at every tier including L1. -->

# `{feature}` `{phase}` plan

Brief description of the proposed feature, change, or refactor.

## Proposed Changes

Describe what work needs to be done at a high level. Reference `{adr}`s,
`{research}`, `{reference}`, and other plan or reference files where
appropriate so implementation remains grounded in architectural decisions.

## Steps

The plan's tier (declared in frontmatter as `tier: L1`, `L2`, `L3`, or
`L4`) determines the structure under this section:

- `L1`: a flat list of Step rows (no Phase, Wave, or Epic).
- `L2`: one or more `### Phase` blocks each containing Step rows.
- `L3`: one or more `## Wave` blocks each containing Phase blocks.
- `L4`: a `## Epic intent` block, followed by Wave blocks.

Replace this scaffold with the tier-appropriate structure for your plan.
Format examples for each block type are embedded below as commented
templates.

<!-- IMPORTANT: This document must be updated between execution runs to
     track progress. -->

Use tasks for simpler features:

- `{Task 1}`
- `{Task 2}`
- `{Task 3}`

## Parallelization

Brief opinion on how tasks might be parallelized, if at all.

## Verification

Clear mission success criteria. Focus on feature coverage against the original
`{adr}`s and `{research}` documents.

Research and ideate on how to ensure besides unit testing that we have
fulfilled our mission.

Example: "Run unit and integration tests (all pass). However, could not
visually confirm that the feature was functional. Further work is required to
implement features to enable better testing." Be honest - tests can be cheated!
