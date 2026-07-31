---
tags:
  - '#exec'
  - '#vault-scale-performance'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
body_hash: 'sha256:e1570866c3abcccb8d6d4f00e8ef7a874f43ba3ed9b9c13e108a7565ea80bc5e'
step_id: 'S04'
related:
  - "[[2026-07-27-vault-scale-performance-plan]]"
---

# reuse the already-built graph and single scan in the status stats path instead of a second VaultGraph build and rescans

## Scope

- `src/vaultspec_core/vaultcore/orientation.py`

## Description

- Add a `graph` parameter to `get_stats` and pass the orientation
  rollup's already-built graph through from
  `src/vaultspec_core/vaultcore/orientation.py`.

## Outcome

The status stats path no longer builds a second complete graph or
fingerprints the corpus twice.

## Notes

None.
