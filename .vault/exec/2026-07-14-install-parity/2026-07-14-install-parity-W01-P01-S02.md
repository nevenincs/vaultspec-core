---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S02'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Add a render_mode aliasing helper that maps DEV to DEPENDENCY and passes TOOL and DEPENDENCY through unchanged, as the single rendering-time comparator

## Scope

- `src/vaultspec_core/core/enums.py`
- `src/vaultspec_core/core/commands.py`

## Description

- Add a module-level `render_mode(mode)` helper in the enums module that returns DEPENDENCY when the declared mode is DEV and otherwise returns the mode unchanged.
- Document the rendering invariant it enforces: DEV is a bookkeeping-only distinction that installs on every `uv sync`, so its launch shape is identical to DEPENDENCY, and no renderer may grow a third branch.
- Note in the docstring that doctor labeling and the committed declaration keep reading the declared mode directly, where the DEV-versus-DEPENDENCY distinction is the point.
- Key `entry_prefix_for_mode` through `render_mode` so the hook-entry prefix table stays a two-shape render surface and the DEV member resolves to the dependency prefix instead of raising a KeyError.

## Outcome

The three-mode model now has exactly one rendering-time comparator, placed in the leaf enums module so both the MCP renderer and the pre-commit hook renderer can import it without an import cycle. Verified: `render_mode(DEV)` is DEPENDENCY, `render_mode(TOOL)` is TOOL, `render_mode(DEPENDENCY)` is DEPENDENCY; `entry_prefix_for_mode(DEV)` returns the `uv run` dependency prefix. Ruff check, ruff format, and scoped ty clean; the collector and workspace-mode unit tests pass (91 passed).

## Notes

Deviation from the row's single-file scope, forced by the plan's phase ordering: the doctor's mode-mismatch collector (`_observed_precommit_mode`) enumerates `for m in InstallMode` and indexes `entry_prefix_for_mode`, so the DEV member added in S01 makes that enumeration raise `KeyError(InstallMode.DEV)` the instant it lands - long before Phase P03's S16 would rewire that renderer. To keep the full CLI suite and `spec doctor` green after every step (the hard non-deviation constraint), this step pulls forward the minimal slice of S16 that DEV's existence forces: aliasing `entry_prefix_for_mode` through `render_mode`. The parallel mode-keyed lookups `hook_defs_for_mode` and the MCP launch table are left untouched here because they are only ever called with a single resolved mode that cannot be DEV until P02 makes DEV resolvable; P03's S15/S16 own their full render_mode wiring and the package parameter.
