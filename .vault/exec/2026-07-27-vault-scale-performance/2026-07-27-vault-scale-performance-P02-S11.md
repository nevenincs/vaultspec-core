---
tags:
  - '#exec'
  - '#vault-scale-performance'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
step_id: 'S11'
related:
  - "[[2026-07-27-vault-scale-performance-plan]]"
---

# exempt the rename integrity check from the single-ingress contract: it validates workspace resources under .vaultspec/, not the vault corpus, so no snapshot routing applies

## Scope

- `src/vaultspec_core/vaultcore/checks/rename_integrity.py`

## Description

- Confirm the rename integrity check reads workspace resources under
  the framework directory, not the vault corpus.

## Outcome

The check is exempt from the corpus single-ingress contract; the
exemption is documented at the run_all_checks wiring.

## Notes

None.
