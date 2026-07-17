---
tags:
  - '#exec'
  - '#mcp-static-launch'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S08'
related:
  - "[[2026-07-17-mcp-static-launch-plan]]"
---

# File the rag-side contract issue covering the tool-spec key and stale-seed refresh, referencing the shared launch-hygiene contract

## Scope

- `repo workflow`

## Description

- File rag issue 231 binding the sibling to the launch-hygiene contract:
  the missing tool-spec key (tool mode silently broken without the mcp
  extra), verification that re-enrollment refreshes pre-parity exe-form
  seeds, and the installer's runtime-dependency placement leak observed
  during this feature's P01 recovery.

## Outcome

Rag-side half of the contract is tracked as rag issue 231, referencing core
PR 224; core carries no rag-release coupling.

## Notes

The static-launch parity itself needs no rag code change - rag entries
render through core's comparator - so the issue is scoped to the builtin
metadata, seed-refresh verification, and the installer placement bug.
