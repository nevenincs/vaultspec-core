---
tags:
  - '#exec'
  - '#vault-scale-performance'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
step_id: 'S14'
related:
  - "[[2026-07-27-vault-scale-performance-plan]]"
---

# memoize the baseline ledger to one read per run and drop per-document path resolution

## Scope

- `src/vaultspec_core/vaultcore/body_schema.py`

## Description

- Add the run-scoped `read_baseline` entry point and a `baseline`
  parameter on `resolve_body_schema`; replace the per-document
  resolve() pair with a lexical relative_to and a resolve fallback.

## Outcome

The attestation ledger reads once per pass, defusing the projected
ninety-second regression on the documented remediation path; path
relativisation stops opening a file handle per document on Windows.

## Notes

Each run still re-reads the ledger from disk, preserving the
review-evidence freshness guarantee the module documents.
