---
tags:
  - '#exec'
  - '#firmware-mcp-primacy'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S21'
related:
  - "[[2026-07-09-firmware-mcp-primacy-plan]]"
---

# Confirm the MCP gateway catalog is byte-unchanged by verifying the command-inventory marker block did not move, reading catalog.py parse against the regenerated reference

## Scope

- `src/vaultspec_core/mcp_server/catalog.py`

## Description

- Run `test_committed_reference_is_in_sync_with_live_surface` and the reference drift suite; report all five nodes green.
- Diff the bundled CLI reference across the whole feature and confirm the only change is the dual-role header paragraph above the marker block.
- Confirm the `vaultspec:generated` command-inventory marker block did not move and stays byte-identical.

## Outcome

The MCP gateway's verb catalog is byte-unchanged. The drift and generated-reference suites pass in full: `test_reference_exists`, `test_every_cli_command_is_in_reference`, `test_every_cli_option_is_in_reference`, `test_p03_surfaced_tokens_are_in_reference`, and `test_committed_reference_is_in_sync_with_live_surface`. The feature-wide diff of the reference shows a single added block, the dual-role header paragraph, inserted well above the `vaultspec:generated:begin command-inventory` marker; the command inventory the gateway parses is identical before and after the feature, so the gateway's `discover` and `invoke` behavior is unchanged.

## Notes

The green drift test is the authoritative proof that only prose outside the generated markers changed; the byte-stable inventory is the constraint the ADR marks inviolate, and it holds.
