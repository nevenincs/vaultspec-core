---
tags:
  - '#exec'
  - '#vault-scale-performance'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
step_id: 'S15'
related:
  - "[[2026-07-27-vault-scale-performance-plan]]"
---

# eliminate the per-document path-syscall storm in the body sections check

## Scope

- `src/vaultspec_core/vaultcore/checks/body_sections.py`

## Description

- Read the attestation ledger once in the body sections check and
  thread it into every schema resolution.

## Outcome

The per-document metadata syscall storm is gone with byte-identical
findings; remaining per-document work is pure string handling.

## Notes

None.
