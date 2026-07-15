---
tags:
  - '#exec'
  - '#provider-mcp-enrollment'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S06'
related:
  - "[[2026-07-15-provider-mcp-enrollment-plan]]"
---

# Add provider-scope MCP controls and provider-native status output

## Scope

- `src/vaultspec_core/cli/spec_cmd.py`
- `src/vaultspec_core/cli/root.py`
- `src/vaultspec_core/core/mcps.py`
- generated CLI reference regions

## Description

- Add provider and scope selection to MCP status and reconciliation.
- Report aggregate and per-provider enrollment, ownership, drift, missing, and external state.
- Add owned-entry uninstall with dry-run and explicit destructive confirmation.
- Group structured reconciliation outcomes by native provider target.
- Describe canonical definitions and provider-native enrollment consistently in live help and generated CLI reference copy.

## Outcome

The MCP CLI now manages Claude, Codex, and Antigravity native targets independently at supported project, local, or user scopes. Status is configuration-only and exposes per-provider health; sync supports force and owned-entry pruning; uninstall removes only recorded ownership. The root sync outcome collector includes the hooks pass and groups MCP outcomes per provider. Ruff and Ty pass, the generated CLI reference is synchronized, and real CLI probes verified project and isolated user-scope operations without dry-run writes.

## Notes

Gemini is intentionally absent from the MCP target list because it has no native MCP capability. Host trust, approval, and process availability remain provider-owned and are not inferred from enrollment status.
