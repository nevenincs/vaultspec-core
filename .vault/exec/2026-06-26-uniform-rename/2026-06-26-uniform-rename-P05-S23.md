---
tags:
  - '#exec'
  - '#uniform-rename'
date: '2026-06-26'
modified: '2026-06-27'
step_id: 'S23'
related:
  - "[[2026-06-26-uniform-rename-plan]]"
---

# Add the rename verb to the local CLI reference

## Scope

- `.vaultspec/rules/reference/cli.md`

## Description

- Refresh the locally-resident CLI reference so its command inventory includes the
  rename verb.
- The managed reference regions are generator-owned: `spec reference generate` emitted
  the verb into the shipped reference during the CLI phase, and `install --upgrade`
  propagated it into the installed `.vaultspec/` reference.

## Outcome

The CLI reference documents `vault feature rename` with its arguments and options.

## Notes

The reference is generator-managed, not hand-authored; the verb appears once the live
CLI surface is regenerated and re-seeded. No manual reference edit was required.
