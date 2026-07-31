---
tags:
  - '#exec'
  - '#vault-scale-performance'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
body_hash: 'sha256:1fb7551b7c73678d34dfeb07404cea7e3fe94fadcffc9ae343383120f9c03e8c'
step_id: 'S12'
related:
  - "[[2026-07-27-vault-scale-performance-plan]]"
---

# memoize per-plan step-id parsing and drop redundant disk probes in the exec mapping check

## Scope

- `src/vaultspec_core/vaultcore/checks/exec_mapping.py`

## Description

- Memoize per-plan step-id parsing and archive probes for the whole
  pass; answer live-plan existence from the snapshot key set; parse
  plans from the ingress text when available.

## Outcome

Each distinct plan parses exactly once regardless of record count
and the calculate phase touches no corpus file.

## Notes

Archive probes remain on disk by design: the archive tree is
excluded from the scanned corpus.
