---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
step_id: S26
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# add CLI tests for link add, remove, and list covering dry-run, JSON envelopes, dangling refusal, and exit codes

## Scope

- `src/vaultspec_core/tests/cli/test_link_cli.py`

## Description

- Created `src/vaultspec_core/tests/cli/test_link_cli.py` with 16 CLI tests using the real Typer runner against real on-disk vault fixtures.
- Tests cover: JSON envelope schema and status for all three verbs, dry-run writes nothing (byte-identical file check), dangling refusal exits 1 without `--force` and succeeds with `--force`, idempotent add returns `unchanged`, no-op remove returns `unchanged`, file mutation verified by reading disk state, and exit codes 0/1.

## Outcome

16 tests pass; ruff and ty checks clean.

## Notes
