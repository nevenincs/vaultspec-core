---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S22'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Layer a minimum_vaultspec_version refuse-and-tell check onto \_resolve_version_warning that hard-refuses with a remediation message when the running package version is below the persisted floor constraint

## Scope

- `src/vaultspec_core/core/resolver.py`

## Description

- Add `_enforce_version_floor`, which reads the committed declaration's `minimum_vaultspec_version` and raises a typed `VaultSpecError` when the running package version parses below the floor, with remediation naming the floor, the running version, and the upgrade command for both modes.
- Treat no declaration, no floor, an unreadable declaration, or unparseable versions as "no constraint" so the floor never turns a benign state into a hard failure.
- Call `_enforce_version_floor` at the top of `_resolve_version_warning`, after the running version and target are resolved but before the manifest-stamp comparison, leaving that softer drift warning intact beneath it.

## Outcome

The workspace now carries an ecosystem-precedented hard floor: an invocation whose running `vaultspec-core` is below the declared `minimum_vaultspec_version` refuses with a remediation message rather than proceeding against a version the workspace has disowned. A probe against the running version (0.1.37) confirmed the thresholds: no floor, a floor of 0.0.1, and a floor equal to the running version all pass silently; a floor of 999.0.0 refuses with the floor, the running version, and the upgrade command in the message. The manifest-stamp advisory continues to fire independently as an informational drift signal. Resolver tests stay green (45 passed).

## Notes

A corrupt declaration is caught inside the floor helper and treated as "no constraint" rather than raising a second, differently-shaped error from the version-check area: declaration corruption already refuses through the explicit install and mode-resolution paths, so surfacing it again here would be redundant and confusing. The floor read targets the committed `workspace.json` declaration (the shared source of truth), not the gitignored manifest echo, matching ADR Q1 and Q4. Because `resolve()` short-circuits for the `DOCTOR` action before `_resolve_version_warning` runs, the floor refusal fires on install, sync, and upgrade flows but not on a bare `doctor` invocation; whether `doctor` should also enforce the floor is noted alongside the S21 doctor-surface observation for the P05 review.
