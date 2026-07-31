---
tags:
  - '#exec'
  - '#vault-scale-performance'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
body_hash: 'sha256:08d6b9059c9511b22588e1b4f1970f47bbf34337197931d8fa46e16695e9b0ff'
step_id: 'S06'
related:
  - "[[2026-07-27-vault-scale-performance-plan]]"
---

# extend the corpus snapshot with raw bytes and per-file metadata so every check can run from it

## Scope

- `src/vaultspec_core/vaultcore/models.py`

## Description

- Add the single ingress read to the graph build: one bytes read per
  document, UTF-8 decode, and universal-newline normalisation
  matching the previous read semantics exactly.
- Retain per-document text and CRLF convention in `raw_texts` and
  read or decode failures in `encoding_issues`; add
  `ensure_raw_texts` so cache-hit builds perform the run's one read
  pass on demand.

## Outcome

Ingress facts survive for the whole run and every converted check
consumes them instead of re-reading the corpus.

## Notes

Raw texts live in memory only and are never serialised into the
graph cache, keeping warm loads lean for non-check consumers; the
snapshot model itself needed no shape change.
