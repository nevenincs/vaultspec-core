---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S19'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Update \_write_mode_declaration and \_infer_upgrade_mode to read and write core's own entry in the v2 packages map via the per-package helpers, preserving sibling package entries untouched

## Scope

- `src/vaultspec_core/core/commands.py`

## Description

- Route `_write_mode_declaration` through the per-package helpers: read and
  write only `vaultspec-core`'s own entry in the shared map via
  `read_package_declaration`/`write_package_declaration`, keeping the floor it
  carried and leaving every sibling package's entry untouched.
- Route `_infer_upgrade_mode`'s already-declared check through
  `read_package_declaration` for core's own entry rather than the whole-core
  facade, so upgrade inference keys on core's map entry explicitly.

## Outcome

Rewriting core's mode during an upgrade preserves both core's own floor and a
companion package's entry intact, verified against a seeded core+rag map where
flipping core to dev left the rag tool-mode entry and its floor untouched and
returned core's preserved floor. The mode-flip and migration-trigger suites (24
tests) pass and `ty check` is clean.

## Notes

The pre-existing integration test `test_upgrade_reseeds_builtins` fails on this
branch independently of this change (it fails on the prior commit too): its
`delete_builtins` factory helper globs the stale nested `rules/rules/` path
rather than the flattened `.vaultspec/rules/` location, so it deletes nothing
and its own assertion fails. It is marked `integration`, outside the unit gate,
and is unrelated to install-parity - flagged for the phase review rather than
fixed here.
