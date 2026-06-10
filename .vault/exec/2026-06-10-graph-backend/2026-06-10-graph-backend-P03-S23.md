---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
step_id: S23
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# implement vault link remove reusing the shared related-entry surgery with dry-run preview

## Scope

- `src/vaultspec_core/cli/link_cmd.py`

## Description

- Implemented `cmd_link_remove` in `src/vaultspec_core/cli/link_cmd.py`.
- Resolves `<src>` via `resolve_related_inputs`; exits 1 on failure.
- Resolves `<dst>` best-effort; falls back to normalised stem for dangling targets.
- No-op (reports `unchanged`) when the edge does not exist - not an error.
- `--dry-run` emits a `removed` envelope without writing.
- Removes the entry via `remove_related_entries` from the shared surgery module; exits 1 on write error.
- JSON envelopes use `vaultspec.vault.link.remove.v1`.

## Outcome

`vault link remove <src> <dst>` fully implemented with no-op detection, dry-run, and JSON envelopes.

## Notes
