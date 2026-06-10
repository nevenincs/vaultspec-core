---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
step_id: S31
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# note the Bash-only mutation path via gh and git as deliberate for this read-write persona without Write or Edit tools (D3)

## Scope

- `src/vaultspec_core/builtins/agents/vaultspec-project-coordinator.md`

## Description

- Append one sentence to the persona's framing paragraph: all mutations flow through
  `gh` and `git` via Bash by design, which is why this read-write persona carries no
  Write or Edit tool (D3)
- Run mdformat --wrap 88 on the edited file

## Outcome

The research's observation that the coordinator is "the only read-write persona
without Write/Edit" is now an explained design choice rather than an anomaly: against
the S30 mode-field definition (declared file-mutation intent via harness tools), the
coordinator's `read-write` mode is exercised exclusively through `gh` and `git`
invocations under Bash, matching its project-management-surfaces-only scope.

## Notes

This closes the D3 decision across all four touched personas: three read-only
return-findings rewordings (S27-S29), the mode-field definition (S30), and the
coordinator's deliberate Bash-only mutation note (S31). No other section of the
coordinator persona needed change.
