---
tags:
  - '#exec'
  - '#vault-scale-performance'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
body_hash: 'sha256:cbc07ac417bc1a3d0126612ca5817b5767fd35088d1a76bcf3ef51252ccda011'
step_id: 'S05'
related:
  - "[[2026-07-27-vault-scale-performance-plan]]"
---

# classify type-filtered listings by path arithmetic instead of parsing every document

## Scope

- `src/vaultspec_core/vaultcore/query.py`

## Description

- Push the concrete doc-type filter into the scan ahead of the file
  read in `src/vaultspec_core/vaultcore/query.py`, deriving the type
  from path arithmetic.

## Outcome

Type-scoped listings read only their own subset of the corpus; plan
and exec listings stop parsing every document.

## Notes

The orphaned and invalid pseudo-types keep the full scan their
graph-backed semantics require.
