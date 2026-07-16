---
tags:
  - '#exec'
  - '#firmware-code-boundary'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S07'
related:
  - "[[2026-07-16-firmware-code-boundary-plan]]"
---

# Propagate builtin edits to the deployed mirror with vaultspec-core sync and confirm spec doctor is clean

## Scope

- `.vaultspec/`

## Description

- Confirm every builtin edit was rolled out through the owning CLI path: each Step ran
  `vaultspec-core install --upgrade` (source to `.vaultspec/` snapshot) and
  `vaultspec-core sync` (snapshot to providers) at edit time.
- Run a final `vaultspec-core sync` and `vaultspec-core spec doctor` as the phase
  gate.

## Outcome

Sync reports the six edited surfaces reconciled with no pending updates; spec doctor
reports every check ok (builtins current, provider dirs complete, migrations applied,
rename integrity consistent, install mode artifacts match).

## Notes

Sync warns about two pre-existing stale `vaultspec-codifier` provider files (present
in `.claude/agents/` and `.gemini/agents/` but absent from the `.vaultspec/` source).
The condition predates this feature and removal requires `sync --force`; left for the
user to decide. Provider directories are gitignored in this repo, so nothing beyond
`src/vaultspec_core/builtins/` and `.vaultspec/` lands in commits.
