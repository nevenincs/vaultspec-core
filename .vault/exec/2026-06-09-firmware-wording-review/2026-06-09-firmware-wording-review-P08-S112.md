---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
step_id: S112
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# unify the execution records versus execution logs naming for the one artifact (D15)

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`

## Description

- Replace "Execution Logs" with "Execution Records" in the Summaries node's depends-on
  line of the Documentation Hierarchy
- Format the rule with mdformat at wrap 88

## Outcome

The Documentation Hierarchy now uses one noun for the one artifact: the Summaries node
depends on Execution Records, matching the hierarchy node of the same name directly
above it, per decision D15. Verification grep for "Execution Logs" across the file
returns zero matches; "Execution Records" is now the only form in the rule.

## Notes

The sibling phrasing "the execution-log artifact" in `system/03-vaultspec.md` is the
scope of P08.S113; the same phrasing also appears in `agents/vaultspec-writer.md`,
which no Step row scopes - noted for the phase summary.
