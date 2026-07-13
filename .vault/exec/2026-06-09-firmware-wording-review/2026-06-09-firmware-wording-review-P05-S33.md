---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S33
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# add the mandatory Critical Requirement code-review section that the standard and high executors carry (D9)

## Scope

- `src/vaultspec_core/builtins/agents/vaultspec-low-executor.md`

## Description

- Append the "## Critical Requirement" section after the Testing Mandate, carrying the
  standard and high executors' wording verbatim: code review via the
  `vaultspec-code-reviewer` persona is mandatory before completion, and the Step is
  not marked complete until the review passes (D9)
- Run mdformat --wrap 88 on the edited file

## Outcome

All three executors now carry the identical mandatory code-review gate. The research
finding that the low executor lacked the section "with no documented exemption" is
resolved by removing the undocumented exemption rather than documenting one: low-risk
Steps still pass the same review gate before closure.

## Notes

The section was placed after the Testing Mandate, mirroring the section order of the
standard and high executors (the low executor keeps its CLI-usage bullet inside the
Core Implementation Mandate; full Documentation-section parallelism is P05.S42).
