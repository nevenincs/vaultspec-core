---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S13'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Add resolver tests asserting the dependency-leak advisory fires for a DEPENDENCY-mode package and stays silent for TOOL or DEV mode

## Scope

- `src/vaultspec_core/tests/cli/test_resolver.py`

## Description

- Add `TestDependencyLeakAdvisory` to the resolver tests, each case passing an explicit `target` at a factory workspace with a written per-package declaration so the advisory is exercised against a known mode rather than the ambient repository context.
- Assert the advisory fires for a DEPENDENCY-mode package on both sync and install, and that it never blocks the plan.
- Assert silence for TOOL mode, for DEV mode, and for a workspace with no declaration at all (confirming the legacy-absent bridge is not consulted).
- Assert silence for the DOCTOR action even in dependency mode (doctor returns the empty plan before any rule) and for the UNINSTALL action (gated to provisioning actions).
- Add a small `_has_leak_advisory` helper keyed on a stable substring of the advisory message.

## Outcome

The warn-only dependency-leak advisory is now pinned on both axes the ADR's D3 cares about: it is present exactly for a declared DEPENDENCY placement under provisioning actions, and absent for every other mode, for an undeclared workspace, and for the doctor and uninstall paths. The doctor-silence case is the direct executable proof of the weighting decision the team required - a dependency-mode workspace's doctor exit code is unaffected - and the tests run against this behavior with a real declaration on the filesystem factory, not a stubbed plan. All 53 resolver unit tests pass (8 new), with `ruff` and `ty` clean. No test doubles or tautologies: each case writes a real `workspace.json` and asserts on the real resolved plan.

## Notes

### Review refinement (ADR D3 moment-of-choice)

P02 code review moved the advisory out of `resolve()` and into the install/upgrade command path so it fires only when a run newly elects dependency mode (see S11's review-refinement note). As a result the `TestDependencyLeakAdvisory` class first added here against `resolve()` no longer matches the mechanism and was removed, and `_signal_warnings` in `test_resolver.py` simplified back to filtering only the version-upgrade nudge. The advisory presence-and-absence coverage now lives where the behavior does: `test_install.py::TestDependencyLeakAdvisory` (explicit and detected dependency install warn; a persisted-declaration reinstall and an `install --dry-run` on a persisted workspace stay silent; tool mode stays silent), plus unit-level `test_workspace_mode.py::TestModeProvenance` and `TestNewlyEstablishesDependency` pinning the provenance tagging and the moment-of-choice predicate (persisted dependency is not newly established; dev and tool never are). All match the canonical advisory constant through one shared marker.
