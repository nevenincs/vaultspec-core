---
tags:
  - '#exec'
  - '#prek-boundary-hardening'
date: '2026-07-23'
modified: '2026-07-23'
body_hash: 'sha256:e300b63773605aed3d26e5fbde55412f59fdf7a8056dbd019abdb12763d1e8cb'
step_id: 'S14'
related:
  - "[[2026-07-23-prek-boundary-hardening-plan]]"
---

# add real-filesystem tests for gated orphan cleanup: removal flag refuses while prek.toml lacks canonical hooks, deletes the YAML once they are present, and the ORPHANED doctor advisory clears afterwards

## Scope

- `src/vaultspec_core/tests/cli/test_convergence_advisories.py`

## Description

- Add TestGatedOrphanCleanup: removal refused (YAML survives) on a conflicting prek.toml, migrate --remove-yaml transplants then deletes and the signal clears to COMPLETE, removal with hooks already present, and migrate without the flag keeping the YAML

## Outcome

Files: `src/vaultspec_core/tests/cli/test_convergence_advisories.py`
