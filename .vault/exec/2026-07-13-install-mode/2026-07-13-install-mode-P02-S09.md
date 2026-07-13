---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S09'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Add WorkspaceFactory-based tests for resolve_install_mode precedence ordering: explicit overrides persisted and detected, persisted overrides detected, and detected overrides default

## Scope

- `src/vaultspec_core/tests/cli/test_workspace_mode.py`

## Description

- Add a `_write_pyproject` helper that writes a minimal `pyproject.toml` with an
  optional dependency list, so precedence tests can plant detection evidence.
- Add `TestResolvePrecedence` with three cases: an explicit flag flips the
  result to tool even when both the persisted declaration and detection point at
  dependency; a persisted tool declaration outranks dependency detection; and
  dependency detection outranks the tool default.

## Outcome

The precedence ordering explicit > persisted > detected > default is now
covered by real on-disk fixtures built through the `factory` fixture (committed
declaration written via the real `write_workspace_declaration`, detection driven
by a real `pyproject.toml`). All three assertions pass; the module holds 13
tests. Ruff is clean.

## Notes

Each precedence case sets the two lower-priority layers to disagree with the
expected result, so a regression that dropped a precedence tier would flip an
assertion rather than pass silently. No mocks, patches, or stubs; the resolver
reads genuine files under the factory root.
