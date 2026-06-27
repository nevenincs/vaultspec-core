---
tags:
  - '#exec'
  - '#uniform-rename'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S13'
related:
  - "[[2026-06-26-uniform-rename-plan]]"
---

# Test validation guards for empty, invalid, reserved target, missing source, and collision refusal

## Scope

- `src/vaultspec_core/vaultcore/tests/test_rename_feature.py`

## Description

- Added `TestValidationGuards` covering empty source, empty target, identical source and target, a non-kebab target (`Bad_Name`), a reserved DocType target (`adr`), a missing source feature, and collision-without-force.
- Each guard asserts a `VaultSpecError` whose message substring is derived from the backend wording, and runs against a real temp vault built with schema-valid documents.

## Outcome

Seven guard tests pass. Every guard refuses before any filesystem mutation occurs.

## Notes

No mocks: each case seeds a real document on disk so the validation path exercises the real feature scanner.
