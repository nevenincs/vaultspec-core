---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S22
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# implement vault link add with target resolution, dangling refusal behind force, and dry-run preview

## Scope

- `src/vaultspec_core/cli/link_cmd.py`

## Description

- Implemented `cmd_link_add` in `src/vaultspec_core/cli/link_cmd.py`.
- Resolves `<src>` and `<dst>` via `resolve_related_inputs`; exits 1 with a `failed` envelope when `<src>` cannot be resolved.
- Refuses to create a dangling edge (target not resolving to a real document) unless `--force` is given; exits 1 on refusal.
- Idempotent: reports `unchanged` when the edge already exists.
- `--dry-run` emits a `created` envelope without writing.
- Appends the entry via `append_related_entry` from the shared surgery module; exits 1 on write error.
- JSON envelopes use `vaultspec.vault.link.add.v1`.

## Outcome

`vault link add <src> <dst>` fully implemented with dangling refusal, idempotency, dry-run, and JSON envelopes.

## Notes
