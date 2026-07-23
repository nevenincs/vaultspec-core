---
tags:
  - '#exec'
  - '#prek-boundary-hardening'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S15'
related:
  - "[[2026-07-23-prek-boundary-hardening-plan]]"
---

# document the new spec precommit verb group in the CLI reference source and roll it out through sync

## Scope

- `src/vaultspec_core/builtins`

## Description

- Regenerate the CLI reference through spec reference generate, picking up the spec precommit group in the generated command inventory
- Roll the refreshed reference out to the workspace mirror via install --upgrade

## Outcome

Files: `src/vaultspec_core/builtins/reference/cli.md`, `docs/CLI.md`, `.vaultspec/reference/cli.md`
