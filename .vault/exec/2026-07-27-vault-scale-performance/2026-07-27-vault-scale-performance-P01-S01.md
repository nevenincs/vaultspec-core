---
tags:
  - '#exec'
  - '#vault-scale-performance'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
body_hash: 'sha256:0b44afc3ca90baff5a3c3f31dd453fe424740f62b3428ee79c45166eb7c5e77a'
step_id: 'S01'
related:
  - "[[2026-07-27-vault-scale-performance-plan]]"
---

# rework fingerprint_vault to the racily-clean rule: trust size+mtime, hash only manifest-write-tick files, keep full-hash as opt-in deep verification

## Scope

- `src/vaultspec_core/graph/cache.py`

## Description

- Rekey warm cache validation on stat trust with a racily-clean hash
  window in `src/vaultspec_core/graph/cache.py`; move full manifest
  hashing to the save path; add the explicit deep-verification flag.
- Rewrite the soundness docstring and the build flow in
  `src/vaultspec_core/graph/api.py` to stat the cache file once and
  validate against its mtime.
- Rework the cache test suite to the new contract with racy-edit,
  accepted-stale-window, and deep-verification cases.

## Outcome

Warm validation no longer hashes the corpus; all 22 cache tests pass;
the accepted residual staleness window is pinned by a dedicated test
together with its deep-verification escape.

## Notes

mtime deltas below filesystem resolution are silently rounded away by
utime; the mtime-change test bumps by a full second.
