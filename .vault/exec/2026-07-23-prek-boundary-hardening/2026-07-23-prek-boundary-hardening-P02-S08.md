---
tags:
  - '#exec'
  - '#prek-boundary-hardening'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S08'
related:
  - "[[2026-07-23-prek-boundary-hardening-plan]]"
---

# add real-filesystem tests for the content-aware states: prek.toml carrying canonical hooks with a stale YAML reports ORPHANED, an empty or hook-less prek.toml reports UNREFRESHABLE, an unparseable prek.toml reports UNREFRESHABLE, and doctor renders the reshaped advisories

## Scope

- `src/vaultspec_core/tests/cli/test_convergence_advisories.py`

## Description

- Add TestPrekContentAwareSignal: healthy prek + stale YAML is ORPHANED, healthy prek + canonical YAML is ORPHANED, healthy prek alone is COMPLETE, empty/partial/unparseable prek.toml is UNREFRESHABLE
- Add TestDoctorPrekAdvisoryText driving spec doctor through the CLI runner over installed workspaces, asserting the migrate-verb and superseded-YAML advisory texts
- Rework the doctor exit-code tests: UNREFRESHABLE now warns (exit 1), ORPHANED never fails (exit 0)
- Extend the enum-membership inventory with ORPHANED

## Outcome

All real-filesystem, no mocks. Files: `src/vaultspec_core/tests/cli/test_convergence_advisories.py`, `src/vaultspec_core/tests/cli/test_signals.py`
