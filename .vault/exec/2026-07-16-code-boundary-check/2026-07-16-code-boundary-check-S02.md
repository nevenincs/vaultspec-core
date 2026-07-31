---
tags:
  - '#exec'
  - '#code-boundary-check'
date: '2026-07-16'
modified: '2026-07-16'
body_hash: 'sha256:73ca8829fb9a42c4785496cae0f819d240eb38f4b567de83473aee1c2676b1aa'
step_id: 'S02'
related:
  - "[[2026-07-16-code-boundary-check-plan]]"
---

# Add the standalone vault check code-boundary subcommand with --json and --feature following the existing standalone-verb pattern

## Scope

- `src/vaultspec_core/cli/vault_cmd.py`

## Description

- Add the standalone `vault check code-boundary` subcommand with `--feature`,
  `--json`, and `--verbose`, following the adr-status standalone-verb pattern
  and the shared render-and-exit path (exit 1 on errors only).

## Outcome

Verb live and advisory. Modified: `src/vaultspec_core/cli/vault_cmd.py`.

## Notes

None.
