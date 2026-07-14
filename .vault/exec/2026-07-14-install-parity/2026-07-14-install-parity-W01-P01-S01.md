---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S01'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Add the DEV member to InstallMode with a docstring describing dev-scoped, non-leaking bookkeeping semantics

## Scope

- `src/vaultspec_core/core/enums.py`

## Description

- Add `DEV = "dev"` as the third `InstallMode` member alongside `TOOL` and `DEPENDENCY`.
- Extend the enum docstring's Members section to describe DEV as dev-scoped placement in the default PEP 735 `dev` group that renders byte-identically to DEPENDENCY but declares distinct, non-leaking bookkeeping.
- State the rendering invariant in the docstring: every renderer collapses DEV onto DEPENDENCY through a single aliasing helper, never a second render path.

## Outcome

DEV is a first-class member of the mode vocabulary. `from_token` already resolves the `dev` token through its lenient `cls(normalized)` path, so no change to token parsing was needed. Verified: `InstallMode.from_token('dev')` returns `InstallMode.DEV`, and the member enumerates after TOOL and DEPENDENCY. Ruff check, ruff format, and scoped ty all clean.

## Notes

No incidents. The render-time aliasing helper this member's docstring references is introduced in the next step; this step adds only the member and its declared semantics.
