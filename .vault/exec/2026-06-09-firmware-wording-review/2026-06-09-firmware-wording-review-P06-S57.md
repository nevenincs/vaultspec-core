---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S57
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# remove the mention of the retired safety auditors persona (D8)

## Scope

- `src/vaultspec_core/builtins/agents/vaultspec-reference-auditor.md`

## Description

- Replace the CRITICAL RULES bullet "DO NOT dispatch safety auditors. That is the
  executor's job." with "DO NOT dispatch review work. Verification at close-out is the
  dispatching orchestrator's responsibility; you return findings only."
- Format with mdformat at wrap 88

## Outcome

The dispatch instruction naming the retired safety-auditors persona is gone from the
reference auditor, the file the research finding and this Step row scope. The
replacement wording is consistent with the post-P05 return-findings contract this
persona received in P05.S29: the auditor is read-only, returns findings as its final
message, and review at close-out belongs to the dispatching orchestrator. A grep
across `src/vaultspec_core/builtins/` finds two remaining "safety auditor" strings,
both in `agents/vaultspec-code-reviewer.md` and both non-referential: a figurative
simile ("the microscopic rigor of a safety auditor") and a provenance note
("Inherited from the legacy Safety Auditor"). Neither instructs dispatching a
persona, and neither is in this Step's scope.

## Notes

None.
