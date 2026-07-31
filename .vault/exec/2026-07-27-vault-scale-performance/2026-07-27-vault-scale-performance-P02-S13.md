---
tags:
  - '#exec'
  - '#vault-scale-performance'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
body_hash: 'sha256:636d2885f6ca25a9fe3bdb7e7eefeafd5950822ed55aa89e40c3bd7b2cd94671'
step_id: 'S13'
related:
  - "[[2026-07-27-vault-scale-performance-plan]]"
---

# precompute index existence and per-feature counts in one snapshot pass, removing the O(features x documents) scan

## Scope

- `src/vaultspec_core/vaultcore/checks/features.py`

## Description

- Collect doc-type sets, per-feature document counts, and the index
  name set in the existing single snapshot pass; delete the
  per-feature full-snapshot helper scans.

## Outcome

The features check is linear in corpus size with identical
findings.

## Notes

None.
