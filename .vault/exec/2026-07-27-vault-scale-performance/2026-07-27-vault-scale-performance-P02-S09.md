---
tags:
  - '#exec'
  - '#vault-scale-performance'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
body_hash: 'sha256:350d1e6f8c1e88c43edb334a37fed4d51478551c0e2be3e5d5039192aa16603b'
step_id: 'S09'
related:
  - "[[2026-07-27-vault-scale-performance-plan]]"
---

# route the encoding check through snapshot raw bytes, folding it into the single ingress read

## Scope

- `src/vaultspec_core/vaultcore/checks/encoding.py`

## Description

- Report encoding findings from the ingress-recorded read and decode
  failures when a graph is supplied; keep the direct disk walk for
  the standalone single-check verb.

## Outcome

The encoding check folds into the run's single read instead of a
whole-corpus byte re-read.

## Notes

A symlinked document observed by the scan is reported on the graph
path rather than skipped; the disk-free contract forbids the
per-file stat parity probes.
