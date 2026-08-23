---
tags:
  - '#exec'
  - '#envelope-optimization'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:41bb0e811d866f84c271f888bcc7cae292f14dbd4179c4a96224ceb18039c770'
step_id: 'S21'
related:
  - "[[2026-08-23-envelope-optimization-plan]]"
---

# Stop disabling the graph cache in feature index generation

## Scope

- `src/vaultspec_core/vaultcore/index.py`

## Description

- Stop disabling the graph cache when re-reading feature membership.

## Outcome

The generator built its graph with the cache disabled, so every call was a full parse of every document - and the repair pipeline calls it once per feature. The mutating path could not take the fix applied to the preview, because omitting the membership argument there is what refreshes membership under the index lock, and that ordering is the property the introducing commit added.

Disabling the cache was pessimism rather than protection. It validates by file set, per-file size and modification time, and a content hash for anything whose timestamp is not older than the cache, and rebuilds on any divergence. It cannot serve a stale membership. The read stays inside the lock; only the redundant re-parse is gone.

A mutating repair over 1,229 documents fell from 125,061 milliseconds to 56,134.

## Notes

Verified equivalent rather than merely faster: identical fixed, error and warning counts, identical generated-index and changed-file totals, identical index paths, and byte-identical index contents between a before and after run on the same fixture.
