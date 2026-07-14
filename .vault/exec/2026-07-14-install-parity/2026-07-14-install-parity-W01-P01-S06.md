---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S06'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Add read_package_declaration and write_package_declaration helpers that read-modify-write a single package's entry under the advisory lock without clobbering sibling packages

## Scope

- `src/vaultspec_core/core/workspace_mode.py`

## Description

- Add `read_package_declaration(target, package)`: reads one named package's entry from the schema 2.0 map by canonicalized distribution name, returning `None` on a missing file or absent entry and propagating strict parse errors.
- Add `write_package_declaration(target, package, declaration)`: under a single advisory lock, reads the current map, replaces only the named package's entry, and rewrites via the lock-free `_write_packages_map`, so a sibling package's entry survives and a legacy single-key file migrates on first write.
- Refactor the two backward-compatible facades to delegate: `read_workspace_declaration` now reads the core entry through `read_package_declaration`, and `write_workspace_declaration` upserts the core entry through `write_package_declaration`, removing the duplicated read-modify-write body.

## Outcome

The module now exposes the per-package API the mixed-configuration model needs while the single-package facades remain byte-transparent over it. Verified with a probe: writing a core entry (dependency, floor 0.1.37) then a rag entry (tool), reading rag back by its underscore spelling, rewriting core as DEV, and confirming the rag entry survives untouched and the facade still returns core's DEV view. Both public writers share one non-reentrant advisory lock via the lock-free `_write_packages_map` primitive, so composing them never self-deadlocks. Workspace-mode, collectors, and migration-trigger unit suites pass (111 passed). Ruff and scoped ty clean.

## Notes

No incidents. The advisory lock is per-path and non-reentrant, so both writers acquire it once and call the lock-free serialization primitive inside the critical section rather than nesting a second acquisition. The manifest module locks its own separate `providers.json` path, so there is no cross-file lock-ordering hazard between the two.
