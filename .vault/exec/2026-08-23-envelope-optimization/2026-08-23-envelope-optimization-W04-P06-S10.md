---
tags:
  - '#exec'
  - '#envelope-optimization'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:d283dc67ab5af6c2c8cc81ff67e38a3cf5e959d674168ac3a2b8616aafef9510'
step_id: 'S10'
related:
  - "[[2026-08-23-envelope-optimization-plan]]"
---

# Forward a limit from the status tool instead of calling the rollup bare

## Scope

- `src/vaultspec_core/mcp_server/tools/orientation.py`

## Description

- Forward the pre-cap total through the orientation result.
- Apply the same cap to the flattened findings of the health check result.
- Report the shown and total counts in the one-line summary.

## Outcome

The orientation tool fell from 274,751 bytes to 5,249 at 10,476 documents. The health check tool fell from 402,967 to 14,075 - it had exceeded a 200,000-token window on its own, against a corpus that is essentially healthy.

## Notes

Per-check counts and aggregate totals are never windowed, so severity arithmetic stays exact however many rows are withheld. A caller always knows the true state of the vault; what it loses is the ability to enumerate every finding in a single response.
