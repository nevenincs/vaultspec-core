---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S21
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# create the vault link command group with the list verb and versioned JSON envelopes

## Scope

- `src/vaultspec_core/cli/link_cmd.py`

## Description

- Created `src/vaultspec_core/cli/link_cmd.py` with `link_app` Typer group and `cmd_link_list` verb.
- `vault link list [<src>]` lists out-links and in-links from the built `VaultGraph`; scoped to `<src>` when given, with `--feature` and `--json` (envelope `vaultspec.vault.link.list.v1`).
- Resolves `<src>` via `resolve_related_inputs`; exits 1 with a `failed` envelope when the source cannot be resolved.
- Group exported as `link_app`; mountable onto `vault_app` by S24.

## Outcome

`src/vaultspec_core/cli/link_cmd.py` created with the `link_app` group and the `list` verb; ruff and ty checks clean.

## Notes
