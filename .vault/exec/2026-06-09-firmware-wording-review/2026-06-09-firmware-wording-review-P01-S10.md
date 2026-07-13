---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-09'
modified: '2026-06-13'
step_id: S10
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# replace the asserted team dispatch tools infrastructure claim at line 82 with hedged coordinated-through-the-host-environment wording (D12)

## Scope

- `src/vaultspec_core/builtins/system/03-vaultspec.md`

## Description

- Replace "using the team dispatch tools" with "coordinated through the host environment" in the Agents section of `src/vaultspec_core/builtins/system/03-vaultspec.md`
- Run mdformat with the 88-column wrap on the edited file

## Outcome

The system fragment no longer asserts team dispatch tooling as shipped infrastructure; the hedged wording matches the coordination-policy framing the team and research skills already use, implementing ADR decision D12.

## Notes

None.
