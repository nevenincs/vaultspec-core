---
tags:
  - '#exec'
  - '#vault-exec-recovery'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S02'
related:
  - "[[2026-07-27-vault-exec-recovery-plan]]"
---

# Recovery command surface

## Scope

- `src/vaultspec_core/cli`

## Description

- Registered `vault exec relink`, `vault exec retire`, and `vault exec detach`.
- Added per-command target, dry-run, JSON envelope, and cache-invalidation behavior.
- Generated the CLI reference inventory through the prescribed generator.

## Outcome

Operators can perform one validated execution-record recovery at a time without hand-editing frontmatter.

## Notes

The command surface delegates all semantic checks and writes to the typed core layer.
