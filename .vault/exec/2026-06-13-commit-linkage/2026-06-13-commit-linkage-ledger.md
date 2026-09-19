---
tags:
  - '#exec'
  - '#commit-linkage'
date: '2026-06-13'
modified: '2026-09-19'
body_schema: 'body-v2'
body_hash: 'sha256:a4ec9ae716690429d259dad66d73c51666e58cf05201aca4c42c05ba2ffff7f1'
related:
  - "[[2026-06-13-commit-linkage-plan]]"
---

# `commit-linkage` ledger

## Changes

- `S01` `A` `src/vaultspec_core/plan/trailer.py`
- `S02` `A` `src/vaultspec_core/cli/plan_cmd.py`
- `S03` `M` `docs/CLI.md`
- `S04` `M` `src/vaultspec_core/tests/plan/test_trailer.py`

## Notes

- `S01` Rows backfilled from the plan's declared Step targets; this ledger was reconstructed after execution, not logged contemporaneously.
