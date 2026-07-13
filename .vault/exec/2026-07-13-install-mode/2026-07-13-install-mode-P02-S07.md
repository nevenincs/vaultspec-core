---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S07'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Add resolve_install_mode implementing the Q5 precedence chain (explicit flag, persisted declaration, pyproject.toml detection, default tool mode) plus the pyproject.toml dependency probe helper

## Scope

- `src/vaultspec_core/core/workspace_mode.py`

## Description

- Add `resolve_install_mode` implementing the Q5 precedence chain: an explicit
  request wins, then the persisted committed declaration, then pyproject
  detection, then the default tool mode.
- Refuse the one impossible combination - explicit dependency mode with no
  `pyproject.toml` - with a typed `VaultSpecError` and a remediation hint, while
  permitting an explicit mode that merely differs from detection evidence.
- Add `_pyproject_declares_vaultspec_dependency`, a lenient `tomllib` probe
  spanning `[project.dependencies]`, `[project.optional-dependencies]`,
  `[dependency-groups]`, and `[tool.uv.dev-dependencies]`.
- Add `_requirement_names` and `_canonical_distribution_name` to normalize PEP
  508 requirement strings per PEP 503 so `vaultspec_core` matches
  `vaultspec-core`.

## Outcome

`resolve_install_mode` is a pure function ready for the install wiring in the
next step. A standalone probe confirmed all eight relevant cases: no-pyproject
default to tool, the dependency-plus-no-pyproject refusal, dependency detection
from both `[project.dependencies]` and an underscore-spelled
`[dependency-groups]` entry, tool default when a pyproject omits vaultspec-core,
the permitted explicit-dependency-differs-from-detection case, persisted
overriding detection, and explicit overriding persisted. Ruff and ty are clean.

## Notes

The probe swallows malformed or unreadable `pyproject.toml` as "no dependency
declared" rather than raising: detection is advisory evidence beneath explicit
and persisted precedence, so a broken manifest must not become a hard failure.
The refusal lives in this function so both the install path and any future
caller inherit the same conflict semantics; the install wiring in the next step
only forwards the explicit flag.
