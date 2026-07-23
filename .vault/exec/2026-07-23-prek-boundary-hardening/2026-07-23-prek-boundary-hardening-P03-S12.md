---
tags:
  - '#exec'
  - '#prek-boundary-hardening'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S12'
related:
  - "[[2026-07-23-prek-boundary-hardening-plan]]"
---

# add operator-gated orphan cleanup: an explicit removal flag on the migration verb that deletes the superseded .pre-commit-config.yaml only after the predicate confirms canonical hooks are present in prek.toml, following the conservative lock-sentinel-prune precedent

## Scope

- `src/vaultspec_core/cli/spec_cmd.py`
- `src/vaultspec_core/core/prek_boundary.py`

## Description

- Gate YAML removal behind the explicit --remove-yaml flag: refusal states return before removal, and a fresh on-disk boundary re-assessment guards the unlink after a real write
- Keep removal a tidiness action: prek silently ignores the YAML, so deletion is never a repair and never automatic

## Outcome

Files: `src/vaultspec_core/core/prek_boundary.py`, `src/vaultspec_core/cli/spec_cmd.py`

## Notes

Automatic (sync-time) deletion stays deferred by decision pending soak of the verified exclusive-read contract.
