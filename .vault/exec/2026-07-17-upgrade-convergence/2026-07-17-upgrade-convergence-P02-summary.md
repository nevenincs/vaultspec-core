---
tags:
  - '#exec'
  - '#upgrade-convergence'
date: '2026-07-17'
modified: '2026-07-17'
related:
  - "[[2026-07-17-upgrade-convergence-plan]]"
---

# `upgrade-convergence` `P02` summary

All three steps closed. Convergence now reaches every legacy workspace
regardless of flags, and the two holes core cannot fix itself surface as
honest warn-only advisories.

- Created: `src/vaultspec_core/migrations/m_0_1_48_launch_convergence.py`, `src/vaultspec_core/migrations/tests/test_launch_convergence.py`, `src/vaultspec_core/tests/cli/test_convergence_advisories.py`
- Modified: `src/vaultspec_core/migrations/__init__.py`, `src/vaultspec_core/core/diagnosis/collectors.py`, `src/vaultspec_core/core/diagnosis/diagnosis.py`, `src/vaultspec_core/core/diagnosis/signals.py`, `src/vaultspec_core/cli/spec_cmd.py`

## Description

The registered migration re-renders recorded project-scope enrollments
through the owning sync verb on the workspace's first contact with any
triggering CLI path, riding the fingerprint-verified refresh so it adds no
force semantics; dogfooded live on this workspace, where it refreshed six
managed entries across three providers and went to applied. The doctor
gains the unrefreshable-hooks and stale-seed advisories with a deliberate
exit-code policy: warn rows that never fail the doctor, because their
remedy lives outside the workspace.
