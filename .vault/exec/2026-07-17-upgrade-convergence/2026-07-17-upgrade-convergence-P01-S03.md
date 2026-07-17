---
tags:
  - '#exec'
  - '#upgrade-convergence'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S03'
related:
  - "[[2026-07-17-upgrade-convergence-plan]]"
---

# Widen the upgrade mode-flip force seam from core-only to every package declared in the workspace map

## Scope

- `src/vaultspec_core/core/commands.py`

## Description

- Read every package's committed workspace declaration via
  `read_package_declarations` instead of hardcoding the core-only set.
- Pass that name set as `force_managed` to the mode-flip seam's `mcp_sync`
  call, falling back to `{"vaultspec-core"}` when no declaration exists.
- Reword the surrounding comment: the seam now covers every declared
  package, and the same-mode divergent case is handled by the
  fingerprint-verified refresh path landed in `mcps.py` rather than left
  fully force-gated.

## Outcome

The upgrade path's mode-flip force seam now migrates every declared
package's managed entry atomically on a mode flip, not only core's. On a
legacy workspace with no declaration the fallback preserves today's
core-only behavior exactly. Existing suites
(`test_mcp_per_package_sync.py`, `test_mcp_provider_files.py`,
`test_install_mode_flip.py`, `test_collectors.py`, 120 tests) pass
unchanged. `ruff check` and `ty check` clean.

## Notes

This step's code change (`src/vaultspec_core/core/commands.py`) was
committed together with `P01.S02`'s commit: a `git add -A` recovery after a
vault-fix pre-commit hook re-staged an already-modified working tree file
alongside the intended S02 files. Both changes were independently reviewed,
tested, and are individually correct; no rework was needed, only this
record's separate closure.
