---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S10'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Add WorkspaceFactory-based tests for the detection signals: absence of pyproject.toml forces tool mode, vaultspec-core listed in project dependencies forces dependency-mode evidence, and absence of both defaults to tool mode

## Scope

- `src/vaultspec_core/tests/cli/test_workspace_mode.py`

## Description

- Add `TestDetectionSignals` covering the detection-only path (no explicit flag,
  no persisted declaration).
- Assert that an absent `pyproject.toml` forces tool mode, that vaultspec-core
  in `[project.dependencies]` is dependency-mode evidence, and that a pyproject
  which omits vaultspec-core (the absence-of-both case) falls through to tool.
- Add a `[dependency-groups]` case using the underscore spelling alongside an
  unrelated requirement to exercise the probe's breadth and PEP 503
  normalization.

## Outcome

Detection is covered end to end by real `pyproject.toml` fixtures under the
factory root. All four cases pass; the module now holds 17 tests. Ruff is clean.

## Notes

The dependency-group case deliberately mixes an unrelated requirement and an
underscore-spelled distribution name so the assertion exercises both the
multi-section probe and the canonical-name comparison rather than a trivially
matching single entry. No mocks or stubs; detection reads genuine files.
