---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S40'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# parameterize the dependency-leak advisory by package so companion installs name the right distribution

## Scope

- `src/vaultspec_core/core/workspace_mode.py`

## Description

The dependency-leak advisory was a hardcoded constant naming vaultspec-core, so
a companion install (vaultspec-rag electing dependency mode) printed misleading
text naming the wrong package - the P06 review's medium finding. The constant
became a private template plus a `dependency_leak_advisory(package)` renderer
defaulting to the core distribution name; `DEPENDENCY_LEAK_ADVISORY` remains as
a byte-identical back-compat constant because vaultspec-rag consumers floored on
0.1.38 reference it directly. Core's two emission sites in `core/commands.py`
(fresh-install resolution and upgrade inference) now call the renderer.

## Outcome

`dependency_leak_advisory("vaultspec-rag")` renders rag-named advisory text;
the default and the legacy constant render byte-identically to the previous
core-named text (asserted by `TestDependencyLeakAdvisoryText`, 3 new tests).
`test_workspace_mode.py` 71 passed; `test_install.py` advisory suite
unchanged and green; ruff, ruff format, and ty clean on all touched files.

## Notes

Rag's W02.P07 rag-side work switches its emission to
`dependency_leak_advisory("vaultspec-rag")` once its floor moves to the core
release carrying this change; until then rag prints the back-compat constant.
