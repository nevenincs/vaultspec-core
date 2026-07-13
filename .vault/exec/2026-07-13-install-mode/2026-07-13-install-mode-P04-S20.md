---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S20'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Add collect_mode_mismatch_state comparing the persisted workspace declaration mode against the observed hook-entry and MCP-command shape, and update collect_precommit_state to derive the expected canonical entries from the persisted mode instead of the hardcoded CANONICAL_HOOK_ENTRIES

## Scope

- `src/vaultspec_core/core/diagnosis/collectors.py`

## Description

- Add `collect_mode_mismatch_state`: read the persisted `.vaultspec/workspace.json` declaration; return `UNKNOWN` when none exists, else compare the declared mode against the observed artifact shapes and return `MISMATCH` on disagreement, `CLEAN` otherwise.
- Add `_observed_precommit_mode`: parse the canonical hook entries and infer their mode from the entry prefix, reading prefixes from `entry_prefix_for_mode` (longest first so the `uvx` prefix wins over any shorter partial), returning `None` when hooks disagree or none are present.
- Add `_observed_mcp_mode`: match the `.mcp.json` `vaultspec-core` server's `command` and `args` against the renderer's own `_MODE_MCP_LAUNCH` table, returning `None` on no match.
- Add a `TYPE_CHECKING` import of `InstallMode` for the helper annotations.
- Wire the collector into `diagnose()` behind the existing exception guard so a malformed workspace degrades to `CLEAN` rather than crashing diagnosis.

## Outcome

The doctor now has a first-class mode-coherence signal that reuses the renderer's own shape sources rather than a second hardcoded copy, honoring the ADR constraint against introducing a parallel comparator. A probe against WorkspaceFactory-built workspaces confirmed both directions: a dependency-mode install reads `CLEAN`, flipping its declaration to tool mode reads `MISMATCH`; a tool-mode install reads `CLEAN`, flipping to dependency reads `MISMATCH`. Collector tests stay green (58 passed).

The S20 row also names updating `collect_precommit_state` to derive the expected canonical entries from the persisted mode. That derivation was already implemented as a P03 pull-forward: `collect_precommit_state` already computes `canonical_hook_entries_for_mode(resolve_render_mode(target))`. This step therefore implements only the new mismatch collector and its diagnose plumbing; no further change to `collect_precommit_state` was needed.

## Notes

`_observed_mcp_mode` reads the renderer's `_MODE_MCP_LAUNCH` table (a module-private within the same `core` package) deliberately, so the launch-shape truth lives in exactly one place; hardcoding a second `uv`/`uvx` mapping here is precisely the drift the decision warns against. A corrupt declaration propagates `VaultSpecError` out of the collector, which the `diagnose()` wrapper catches and logs, keeping doctor read-only and crash-free.
