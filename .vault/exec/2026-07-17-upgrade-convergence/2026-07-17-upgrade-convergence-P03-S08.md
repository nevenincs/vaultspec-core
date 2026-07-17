---
tags:
  - '#exec'
  - '#upgrade-convergence'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S08'
related:
  - "[[2026-07-17-upgrade-convergence-plan]]"
---

# Reconcile doctor hints, sync summaries, and the MCP doc convergence passage with the automatic behavior, exceptions, and opt-outs

## Scope

- `docs/MCP.md`

## Description

- Replace the MCP doc's manual-refresh remediation with a dedicated
  convergence-on-upgrade section: automatic fingerprint-verified refresh
  with narrated output, the migration trigger on first CLI contact
  regardless of provisioned version, the hand-edited and pre-fingerprint
  exceptions, the external-entry boundary, the skip-mcp opt-out, and the
  two warn-only doctor advisories.
- Audit the in-code hint strings: the mode-mismatch resolver hint and the
  merge warnings are already truthful after the engine change (upgrade and
  sync now genuinely converge); the no-fingerprint skip warning gained its
  honest force wording in the engine step.

## Outcome

Every user-facing description of upgrade and sync behavior matches what
the commands now do; no surface promises a remediation that does not work.

## Notes

None.
