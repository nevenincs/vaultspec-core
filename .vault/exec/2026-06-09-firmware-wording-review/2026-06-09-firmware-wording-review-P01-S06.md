---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-09'
modified: '2026-06-09'
step_id: S06
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# add the missing Audit node to the Documentation Hierarchy so the ADR and Plan depends-on-audits links resolve (D2)

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`

## Description

- Insert an Audits node into the Documentation Hierarchy of `src/vaultspec_core/builtins/rules/vaultspec.builtin.md` between the Brainstorm/Research node and the ADR node
- Mirror the sibling node style with Depends-on and References sub-bullets and carry both the canonical and the narrative-infix filename forms
- Run mdformat on the edited file

## Outcome

The hierarchy now contains an Audit node positioned above ADRs and Plans, so their existing "Depends on: audits" entries resolve to a defined node, implementing ADR decision D2.

## Notes

The node lists "Depends on: brainstorm, research" and "References: the artifacts under review" to keep the hierarchy's lower-references-upper convention intact while acknowledging that review-phase audits point at plans and execution records.
