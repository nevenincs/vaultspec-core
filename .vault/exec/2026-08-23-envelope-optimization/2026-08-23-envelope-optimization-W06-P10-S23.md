---
tags:
  - '#exec'
  - '#envelope-optimization'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:4e33426272a3dad1830deee2dcb0038d829969ed5ef9ac619ca42373af29ca9c'
step_id: 'S23'
related:
  - "[[2026-08-23-envelope-optimization-plan]]"
---

# Remove the per-feature graph rebuild from the mutating index refresh while keeping the under-lock membership guarantee

## Scope

- `src/vaultspec_core/vaultcore/repair.py`

## Description

- Record the mutating refresh's remedy and the guarantee it must preserve.

## Outcome

The mutating index refresh is addressed by enabling the graph cache rather than by passing shared membership, and the reasoning is recorded at the call site so the distinction is not lost to a later reader.

The preview branch holds no lock, so passing shared membership there is safe. The mutating branch takes a real advisory lock and re-reads membership under it. Copying the preview's fix would have looked obvious and quietly defeated the guarantee the introducing commit was added to provide.

## Notes

The introducing commit was itself a correctness fix, for body-hash integrity across rewrites. Neither change here is a revert of it, and neither weakens it.
