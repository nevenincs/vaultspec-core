---
tags:
  - '#exec'
  - '#uniform-rename'
date: '2026-06-26'
modified: '2026-06-27'
body_hash: 'sha256:007fb2856d25e8dcd9b1d9c1f216a4dc5951e7e397021225696b801f84f5decb'
step_id: 'S22'
related:
  - "[[2026-06-26-uniform-rename-plan]]"
---

# Document the vault feature rename verb in the CLI mandate rule

## Scope

- `.vaultspec/rules/rules/vaultspec-cli.builtin.md`

## Description

- Add the `vault feature rename <old> <new>` verb to the CLI mandate rule's command
  inventory, beside the feature archive verb, describing the surfaces it rewrites,
  its atomic-with-rollback apply, and the `--force` merge.
- Edit the shipped builtin source rather than the installed copy, then re-seed.

## Outcome

The CLI mandate rule documents the rename verb across the shipped builtins and the
self-installed workspace.

## Notes

The plan scope names the installed `.vaultspec/` copy, but the canonical edit target is
the builtin source under `src/vaultspec_core/builtins/rules/`; `install --upgrade`
re-seeds the change into `.vaultspec/`. Provider mirrors are gitignored and regenerated.
