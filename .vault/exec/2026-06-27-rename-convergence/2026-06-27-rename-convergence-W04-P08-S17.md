---
tags:
  - '#exec'
  - '#rename-convergence'
date: '2026-06-27'
modified: '2026-06-27'
step_id: 'S17'
related:
  - "[[2026-06-27-rename-convergence-plan]]"
---

# Document the converged rename verbs and the new check in the CLI mandate rule

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec-cli.builtin.md`

## Description

- Review the CLI mandate rule's command inventory against the new check.

## Outcome

- Left the mandate rule unchanged. The verify-and-audit section lists verbs plus the feature-scoped feature-completeness check, but no specialized checks: the encoding, rename-integrity, and structure checks are all absent and covered by `vault check all` and the generated CLI reference. Adding the new check would not fit the existing command-inventory style and would over-edit, so the rule relies on the regenerated reference instead.

## Notes

- No formatting pass was needed because the rule was not edited. The decision matches the precedent set by the sibling encoding check, which is likewise not individually listed in the mandate rule.
