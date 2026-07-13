---
tags:
  - '#exec'
  - '#firmware-mcp-primacy'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S10'
related:
  - "[[2026-07-09-firmware-mcp-primacy-plan]]"
---

# Reword the standard-executor Scaffold and step-state mandates to lead with the capability sentence while keeping the exact vault add exec and vault plan step check/uncheck verbs, dropping toggle from the recommended set, leaving the tools allowlist byte-identical

## Scope

- `src/vaultspec_core/builtins/agents/vaultspec-standard-executor.md`

## Description

- Reword the standard-executor Scaffold mandate to lead with the capability sentence (scaffold before authoring so the filename and step_id are machine-filled), keeping the exact vault add exec verb.
- Retitle the step-state mandate and lead with the capability (update state through the owning plan verb, never the checkbox glyph), keeping the exact vault plan step check and uncheck verbs.
- Drop the toggle verb from the recommended step-state set, matching the tool surface's explicit-state stance.
- Leave the tools allowlist byte-identical.

## Outcome

- The standard-executor's Scaffold and step-state mandates now lead with capability while retaining every exact CLI verb; toggle is dropped and the allowlist is unchanged.

## Notes

- None.
