---
tags:
  - '#exec'
  - '#firmware-mcp-primacy'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S01'
related:
  - "[[2026-07-09-firmware-mcp-primacy-plan]]"
---

# Rewrite the CLI rule in place: transport-neutral Mandate, nine-tool capability map, Q6 three-band CLI-or-gateway list, two-line CLI-fallback runtime block, single file-level fallback clause, and orientation and allowed-edits sections reworded to name the status and find tools as primary, targeting roughly half the current length

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec-cli.builtin.md`

## Description

- Rewrite the always-on CLI rule in place at the same filename, roughly halving its length.
- Recast the Mandate as transport-neutral: all vault operations route through owning-verb logic, MCP tools primary where connected and the CLI otherwise.
- Collapse the twenty-command catalog into a nine-tool capability map plus the three-band CLI-or-gateway list from the honesty scheme.
- Reword Orientation to name the status and find tools as the primary orientation path, with the status CLI form retained.
- Shrink the runtime block to a two-line CLI fallback under an explicit CLI fallback heading and add one file-level fallback clause.
- Keep the Allowed manual edits section, retargeting its scaffold mention at the create tool with the CLI verb retained.

## Outcome

- The CLI rule drops from 5219 to 3389 characters (116 to 67 lines); it reads correctly connected (hot tools named primary) and disconnected (single fallback clause plus catalog pointer), with no availability conditional, no MCP claim for the denylisted verbs, and gateway-only verbs marked CLI-first.

## Notes

- Character reduction lands near 65 percent of the original by bytes and 58 percent by lines, within the roughly-half target.
