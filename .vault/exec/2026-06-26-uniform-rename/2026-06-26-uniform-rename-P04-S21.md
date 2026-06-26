---
tags:
  - '#exec'
  - '#uniform-rename'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S21'
related:
  - "[[2026-06-26-uniform-rename-plan]]"
---

# Test the rename command end-to-end including the json envelope

## Scope

- `src/vaultspec_core/tests/cli/test_feature_rename_cli.py`

## Description

- Added `test_feature_rename_cli.py` driving the real Typer command through `WorkspaceFactory` plus the `CliRunner` against a real installed workspace and a schema-valid feature corpus.
- Assert `vault feature rename old new` exits 0 with human output that mentions the rename and a clean `vault check all` afterwards; assert `--json` yields `schema == vaultspec.vault.feature.rename.v1` and `status == updated`; assert a collision run without `--force` exits non-zero with a `failed` envelope.

## Outcome

Three tests pass. The command renames cleanly, the JSON envelope matches the versioned contract, and the refusal path returns a parseable failure.

## Notes

The corpus is connected (research, adr, plan, audit, exec records, generated index) so `vault check all` is fully clean both before and after the rename.
