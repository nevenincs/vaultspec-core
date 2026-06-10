---
generated: true
tags:
  - '#index'
  - '#cli-reference-automation'
date: '2026-06-10'
related:
  - '[[2026-06-10-cli-reference-automation-P01-S01]]'
  - '[[2026-06-10-cli-reference-automation-P01-S02]]'
  - '[[2026-06-10-cli-reference-automation-P01-S03]]'
  - '[[2026-06-10-cli-reference-automation-P01-summary]]'
  - '[[2026-06-10-cli-reference-automation-P02-S04]]'
  - '[[2026-06-10-cli-reference-automation-P02-S05]]'
  - '[[2026-06-10-cli-reference-automation-adr]]'
  - '[[2026-06-10-cli-reference-automation-plan]]'
---

# `cli-reference-automation` feature index

Auto-generated index of all documents tagged with `#cli-reference-automation`.

## Documents

### adr

- `2026-06-10-cli-reference-automation-adr` - `cli-reference-automation` adr: `cli reference auto-generation` | (**status:** `accepted`)

### exec

- `2026-06-10-cli-reference-automation-P01-S01` - Add a removal-milestone marker to the legacy template-name fallback so the ref-audit.md grace path is scheduled for removal one release after the rename, keeping the existing five fallback tests green (REVIEW-005 fallback)
- `2026-06-10-cli-reference-automation-P01-S02` - Relocate the in-function current-name template mapping to module scope beside \_LEGACY_TEMPLATE_NAMES for symmetry, keeping tests green (REVIEW-005 fallback)
- `2026-06-10-cli-reference-automation-P01-S03` - Correct the vault add --feature required-marker annotation to match live --help and grep the reference for any other stale required-markers (P03 doc gap)
- `2026-06-10-cli-reference-automation-P01-summary` - `cli-reference-automation` `P01` summary
- `2026-06-10-cli-reference-automation-P02-S04` - Produce a decision ADR weighing a Typer-surface auto-generator for the bundled reference against the existing hand-authored-plus-drift-guard approach, deciding whether to build it (D6 deferral)
- `2026-06-10-cli-reference-automation-P02-S05` - GATED on the ADR deciding build, implement the generator and wire it into the pre-commit and CI surface beside the drift guard, regenerating the bundled reference from the live Typer tree with covering tests (D6 deferral)

### plan

- `2026-06-10-cli-reference-automation-plan` - `cli-reference-automation` plan
