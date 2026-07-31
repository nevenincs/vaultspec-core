---
tags:
  - '#exec'
  - '#firmware-mcp-primacy'
date: '2026-07-09'
modified: '2026-07-10'
body_hash: 'sha256:ac85f9511c53fad53a7c90addb8fdf512b17a55d36c3a042c2043e14af65a77a'
step_id: 'S11'
related:
  - "[[2026-07-09-firmware-mcp-primacy-plan]]"
---

# Reword the low-executor Scaffold and step-state mandates to lead with the capability sentence while keeping the exact vault add exec and vault plan step check/uncheck verbs, dropping toggle from the recommended set, leaving the tools allowlist byte-identical

## Scope

- `src/vaultspec_core/builtins/agents/vaultspec-low-executor.md`

## Description

- Reword the low-executor Scaffold mandate to lead with the capability sentence, keeping the exact vault add exec verb.
- Retitle the step-state mandate and lead with the capability, keeping the exact vault plan step check and uncheck verbs.
- Drop the toggle verb from the recommended step-state set.
- Leave the tools allowlist byte-identical.

## Outcome

- The low-executor's Scaffold and step-state mandates now lead with capability while retaining every exact CLI verb; toggle is dropped and the allowlist is unchanged.

## Notes

- The edit is textually identical to the standard- and high-executor passes, preserving the shared persona voice.
