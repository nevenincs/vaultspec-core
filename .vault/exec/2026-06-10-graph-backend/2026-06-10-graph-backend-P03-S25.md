---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
modified: '2026-06-13'
body_hash: 'sha256:f296c142020fa9a8db2cf5f051bee35060301383dccc135ee6075f703ce3af8e'
step_id: S25
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# add CRLF-preservation, atomic-write, and round-trip tests for the shared surgery helper

## Scope

- `src/vaultspec_core/vaultcore/tests/test_link_surgery.py`

## Description

- Created `src/vaultspec_core/vaultcore/tests/test_link_surgery.py` with 17 tests covering CRLF preservation, LF correctness, atomic write (no stray `.bak` files), idempotency, round-trip restore, case-insensitive matching, empty-related-list append, `ValueError` on empty stem, and no-op on missing file.
- Tests write real on-disk files with explicit CRLF or LF byte-level encoding and assert byte-level invariants.

## Outcome

17 tests pass; ruff and ty checks clean.

## Notes
