---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
modified: '2026-06-13'
body_hash: 'sha256:7fe32f5ceb93ad082dc4f59c4848ea5b5c4fcf468cf7da0dbf54e2f73952872a'
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
