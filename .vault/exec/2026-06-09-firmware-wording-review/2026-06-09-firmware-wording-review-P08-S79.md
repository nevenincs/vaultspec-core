---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S79
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# fix the fundations and considere-null-and-void typos and supply the missing conjunction at line 20 (D15)

## Scope

- `src/vaultspec_core/builtins/skills/vaultspec-adr/SKILL.md`

## Description

- Correct "fundations" to "foundations" in the when-to-use bullet about decisions
  affecting the project's foundations
- Correct "considere null and void" to "considered null and void" in the CRITICAL
  user-approval workflow bullet
- Supply the missing conjunction in the blast-radius bullet: "the blast radius,
  "why", "what"" becomes "the blast radius, "why", and "what""
- Format the skill with mdformat at wrap 88

## Outcome

The three typo-inventory items the research charged to this file are resolved per
decision D15. Verification grep across the file for `fundations`, the bare
misspelling `considere`, and the conjunction-less `"why", "what"` sequence returns zero
matches; the corrected forms read naturally in context.

## Notes

None.
