---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S24
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# register the link group on the vault command app and wire the exit-code contract

## Scope

- `src/vaultspec_core/cli/vault_cmd.py`

## Description

- Added `from vaultspec_core.cli.link_cmd import link_app` and `vault_app.add_typer(link_app, name="link")` to `src/vaultspec_core/cli/vault_cmd.py`.
- Ran `vaultspec-core spec reference generate` to regenerate the managed regions of `src/vaultspec_core/builtins/reference/cli.md` and `docs/CLI.md` with the new `vault link` group and its three verbs.
- Confirmed `vaultspec-core spec reference generate --check` exits zero.

## Outcome

`vault link` group registered on the vault command app; CLI reference regenerated and in sync; exit-code contract (0 success/no-op, 1 failure) inherited from link verbs.

## Notes
