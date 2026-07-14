---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S14'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Add a package parameter to resolve_render_mode, reading only that package's own entry from the v2 map, with the legacy-absent DEPENDENCY bridge as the default package's fallback

## Scope

- `src/vaultspec_core/core/workspace_mode.py`

## Description

- Add a `package` parameter to `resolve_render_mode`, defaulting to the core
  distribution, so each package resolves its render mode from its own entry in
  the shared per-package map rather than always reading core's.
- Switch the body from the core-only `read_workspace_declaration` facade to the
  per-package `read_package_declaration`, keeping the legacy-absent
  `DEPENDENCY` bridge as the fallback for an absent entry.
- Add a public `read_package_declarations` accessor returning every declared
  package's entry, the enumeration the per-package doctor rows consume.
- Export a public `CORE_DISTRIBUTION_NAME` constant aliasing the internal
  private name, so callers outside the module can address core's own entry
  without importing a private.

## Outcome

`resolve_render_mode(target, package)` reads only the named package's entry; a
schema 2.0 file carrying only a sibling entry reads as absent for the queried
package and falls through to the dependency bridge, exactly as a pre-declaration
file does. Core's zero-argument behaviour is byte-identical. The 68
workspace-mode unit tests pass and `ty check` is clean.

## Notes

No incidents. Sibling-preservation and mixed-package render behaviour are
exercised by the S20 test step.
