---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S04
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# bump the graph envelope schema to vaultspec.vault.graph.v2

## Scope

- `src/vaultspec_core/cli/vault_cmd.py`

## Description

- Added an optional `version: int = 1` keyword parameter to `json_envelope()` in `src/vaultspec_core/cli/rendering.py`; the schema string is now `f"vaultspec.{command}.v{version}"`.
- Updated the `json_envelope` docstring with the new parameter, its default, and worked examples.
- Updated `cmd_graph` in `src/vaultspec_core/cli/vault_cmd.py` to pass `version=2`; the emitted schema is now `vaultspec.vault.graph.v2`.
- All existing callers of `json_envelope` that do not pass `version` continue to emit `.v1` unchanged.

## Outcome

The graph JSON envelope now carries `"schema": "vaultspec.vault.graph.v2"`. No compatibility shim is needed; the ADR gate confirmed no v1 consumers exist. All 1102 tests pass across graph and CLI suites.

## Notes

No incidents. The `version` parameter defaults to 1 so the change is backward-compatible for all non-graph callers.
