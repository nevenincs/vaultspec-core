---
tags:
  - '#exec'
  - '#vault-scale-performance'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
body_hash: 'sha256:c01c1ea075d5bd7175111bc8b64aa0d204f364a0c6637e3fe4d2b670479f05b8'
step_id: 'S03'
related:
  - "[[2026-07-27-vault-scale-performance-plan]]"
---

# default the MCP find graph build to the warm cache

## Scope

- `src/vaultspec_core/mcp_server/tools/documents.py`

## Description

- Switch the create-path feature-index regeneration in
  `src/vaultspec_core/mcp_server/tools/documents.py` from a forced
  cold build to the fingerprint cache.

## Outcome

The last cold graph build in the MCP surface now reads warm and
refreshes the cache for the next call; the find path already used
the cache in this tree.

## Notes

Fresh document writes invalidate via size or mtime, so the cold
bypass was never needed for correctness.
