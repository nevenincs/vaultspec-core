---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S27
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# regenerate the bundled CLI reference and propagate provider sync

## Scope

- `.vaultspec/rules/reference/cli.md`

## Description

- Ran `vaultspec-core spec reference generate`: reported "Generated references already up to date: cli.md, CLI.md." (no changes needed; S24 already regenerated on registration).
- Ran `vaultspec-core sync`: 102 unchanged.
- Confirmed `vaultspec-core spec reference generate --check` exits zero with "Generated references in sync: cli.md, CLI.md."
- Working tree clean; no additional commits required.

## Outcome

CLI reference in sync; `--check` exits zero. No residual drift.

## Notes
