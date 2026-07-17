---
tags:
  - '#exec'
  - '#code-boundary-check'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S01'
related:
  - "[[2026-07-16-code-boundary-check-plan]]"
---

# Implement the code-boundary checker module: needle enumeration from vault stems, excluded-dir source walk, decode guard, size cap, WARNING diagnostics

## Scope

- `src/vaultspec_core/vaultcore/checks/code_boundary.py`

## Description

- Implement the checker: needle enumeration from vault document stems
  (including index stems), iterative excluded-dir source walk with symlink
  skip, UTF-8 decode guard, 1 MB size cap, one WARNING diagnostic per hit
  file naming the matched stems; export from the checks package without
  touching the check-all membership.

## Outcome

Scanner authority in one module; advisory by construction (warnings only,
`supports_fix` false). Created:
`src/vaultspec_core/vaultcore/checks/code_boundary.py`.

## Notes

None.
