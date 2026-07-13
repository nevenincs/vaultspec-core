---
tags:
  - '#exec'
  - '#firmware-mcp-primacy'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S06'
related:
  - "[[2026-07-09-firmware-mcp-primacy-plan]]"
---

# Replace the MUST plan-verbs paragraph with the ADR Q4 after-form verbatim, keeping the owning-verb invariant in the MUST position and naming the plan_progress and plan_edit tools as primary with the CLI as the above-Step and disconnected-session path

## Scope

- `src/vaultspec_core/builtins/system/03-vaultspec.md`

## Description

- Replace the MUST plan-verbs paragraph in the system prompt with the ADR Q4 after-form verbatim.
- Keep the owning-verb, never-hand-edits invariant in the MUST position.
- Name the plan_progress tool for Step completion and the plan_edit tool for Step rows as the primary path.
- Route above-Step structural changes and any MCP-less session through the vault plan CLI verbs, preserving the canonical-identifier and gap-no-reuse guarantee.

## Outcome

- The strongest plan mandate now reads as the Q4 after-form: shorter, true in both worlds, honest about the above-Step gateway-only gap, and with the invariant kept in the MUST position.

## Notes

- The prior trailing sentences (canonical surface preamble, help pointer) were absorbed into the shorter after-form rather than retained, matching the verbatim replacement instruction.
