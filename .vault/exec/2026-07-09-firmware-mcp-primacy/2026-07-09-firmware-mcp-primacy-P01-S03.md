---
tags:
  - '#exec'
  - '#firmware-mcp-primacy'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S03'
related:
  - "[[2026-07-09-firmware-mcp-primacy-plan]]"
---

# Read the two reworded rule files through in both the MCP-connected and disconnected readings and confirm no conditional-availability logic, no false MCP coverage for denylisted verbs, and no hot-tool claim for gateway-only verbs

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec-cli.builtin.md`

## Description

- Read both reworded rule files through in the MCP-connected reading: the hot tools are named primary and the capability map reads as the operative surface.
- Read both through in the disconnected reading: the single file-level fallback clause plus the CLI-fallback runtime and catalog pointer give a complete CLI path.
- Confirm no conditional-availability logic is present in either file.
- Confirm the denylisted verbs (feature index, spec mcps mutation, uninstall) are worded CLI-only with no implied MCP coverage.
- Confirm the gateway-only verbs (sync, spec resource sync, above-Step plan verbs) are worded CLI-first, never as hot tools.

## Outcome

- Both rule files pass the two-world read-through: correct connected and disconnected, no availability conditional, no false MCP coverage for denylisted verbs, and no hot-tool claim for gateway-only verbs.

## Notes

- This read-through is the Phase P01 verification; the mandatory closeout code review remains scoped to P05.
