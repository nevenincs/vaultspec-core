---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S05'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Rewrite write_workspace_declaration to serialize the v2 packages map canonically with sorted keys and the schema_version 2.0 stamp

## Scope

- `src/vaultspec_core/core/workspace_mode.py`
- `src/vaultspec_core/tests/cli/test_workspace_mode.py`

## Description

- Add `_write_packages_map`, the single lock-free write primitive that serializes the `{"schema_version": "2.0", "packages": {...}}` envelope canonically (sorted keys via `json.dumps(sort_keys=True)`, two-space indent, trailing newline) and omits an unset floor rather than writing a null.
- Rewrite `write_workspace_declaration` as the compat facade: under one advisory lock it reads the current map, upserts only the `vaultspec-core` entry from the single-package `WorkspaceDeclaration`, and rewrites in schema 2.0 shape, leaving companion entries untouched and migrating a legacy single-key file on first write.
- Update the `test_write_is_canonical` touched test to assert the v2 nested shape (schema_version at the top level, `install_mode` and `minimum_version` inside the `packages["vaultspec-core"]` entry, both key sets sorted).

## Outcome

Writes now emit the schema 2.0 per-package envelope, closing the S03-S05 interim where the body was still single-key. Verified with a probe: seeding a mixed map (core tool-mode, rag dependency-mode with a floor) then writing core as DEV through the facade preserves the rag entry verbatim, persists `install_mode: dev`, and emits canonical sorted bytes. The lock-free primitive composes inside the facade's own advisory-lock critical section without re-entering the non-reentrant lock. Workspace-mode, collectors, migration-trigger, and install-mode-flip unit suites pass (115 passed). Ruff and scoped ty clean.

## Notes

Only one existing test asserted the raw wire shape (`test_write_is_canonical`); it was updated in place as a touched test. The other round-trip and corrupt-declaration tests read through the `WorkspaceDeclaration` facade or a legacy raw body and stayed green unchanged. The per-package public helpers that generalize this read-modify-write are added in S06, which then refactors this facade to delegate to them.
