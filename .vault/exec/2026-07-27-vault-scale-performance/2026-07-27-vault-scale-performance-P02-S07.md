---
tags:
  - '#exec'
  - '#vault-scale-performance'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
step_id: 'S07'
related:
  - "[[2026-07-27-vault-scale-performance-plan]]"
---

# route the annotations check through the shared snapshot

## Scope

- `src/vaultspec_core/vaultcore/checks/annotations.py`

## Description

- Accept the ingress raw-text map in the annotations check and
  validate from it on non-mutating passes; share the standalone
  read fallback through `iter_document_texts`.

## Outcome

Non-mutating passes are corpus-disk-free with identical findings;
the mutating fix path still reads what it rewrites.

## Notes

Lone-CR newline conventions are now normalised the same way every
read_text consumer already normalised them.
