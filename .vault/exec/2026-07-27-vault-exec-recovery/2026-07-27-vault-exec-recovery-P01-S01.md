---
tags:
  - '#exec'
  - '#vault-exec-recovery'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:6d677c82afe3a3d974833a867182c244fbd43202e82270bbb35d481f663f45a7'
step_id: 'S01'
related:
  - "[[2026-07-27-vault-exec-recovery-plan]]"
---

# Typed recovery operations

## Scope

- `src/vaultspec_core/vaultcore`

## Description

- Added typed relink, retire, detach, and parent-resolution operations.
- Preserved record bodies and line endings while changing only machine-owned metadata.
- Added containment, archive collision, and lock-backed concurrency protections.

## Outcome

The core recovery layer validates one live parent plan and applies only the explicit recovery allowed by the accepted ADR.

## Notes

Independent review found and verified fixes for archive, path, line-ending, and concurrency boundaries before release.
