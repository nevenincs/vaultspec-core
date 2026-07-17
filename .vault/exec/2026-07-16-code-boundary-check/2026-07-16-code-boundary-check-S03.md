---
tags:
  - '#exec'
  - '#code-boundary-check'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S03'
related:
  - "[[2026-07-16-code-boundary-check-plan]]"
---

# Add unit tests covering stem and wiki-link hits, literal-path non-hit, exclusions, feature filter, skip guards, and advisory exit code

## Scope

- `src/vaultspec_core/vaultcore/checks/tests/test_code_boundary.py`

## Description

- Add real-filesystem checker tests (stem and wiki-link hits, literal vault
  path non-hit, vault/harness/provider exclusions, feature filter, decode and
  size skip guards, index-stem needle, empty vault) and CLI verb tests
  (findings exit 0, clean tree reports clean).

## Outcome

10 tests green (8 checker + 2 CLI).

## Notes

None.
