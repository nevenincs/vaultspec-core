---
tags:
  - '#exec'
  - '#vault-scale-performance'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
body_hash: 'sha256:04219012757eeffc1ff3a55e76a6d0a459e1fa89c4482d986f4698e0d9a5487a'
step_id: 'S08'
related:
  - "[[2026-07-27-vault-scale-performance-plan]]"
---

# route the markdown check through the shared snapshot

## Scope

- `src/vaultspec_core/vaultcore/checks/markdown.py`

## Description

- Accept the ingress raw-text map in the markdown hygiene check and
  validate from it on non-mutating passes, mirroring the annotations
  conversion.

## Outcome

Non-mutating passes are corpus-disk-free with identical findings.

## Notes

None.
