---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S15'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Update \_scaffold_precommit to read the resolved workspace mode and render hook entries through the mode-parameterized hook definitions

## Scope

- `src/vaultspec_core/core/commands.py`
- `src/vaultspec_core/core/diagnosis/collectors.py`

## Description

- Add a `mode` parameter to `_scaffold_precommit`; when absent, resolve it from the committed declaration via `resolve_render_mode` (dependency mode for a legacy workspace), and render the canonical hook set for that mode.
- Replace the three uses of the module-level dependency-pinned hook list inside the scaffolder with the mode-rendered list.
- Thread the fresh-install resolved mode into the scaffolder through `init_run` and the install dry-run preview so a fresh tool-mode install writes `uvx` hook entries.
- Derive `collect_precommit_state`'s expected hook entries from the workspace's resolved mode instead of the dependency-pinned constant, so a correctly-provisioned tool-mode workspace is not diagnosed as non-canonical.

## Outcome

The pre-commit scaffolder now renders hook entries for the resolved provisioning mode. A fresh install with no `pyproject.toml` provisions tool mode and writes the four `uvx --from vaultspec-core vaultspec-core ...` hook entries; a dependency-mode install writes the unchanged `uv run --no-sync vaultspec-core ...` entries. Both were verified end to end against a synthetic install. The doctor's canonical-entry check now expects the mode the workspace actually declares, so `spec doctor` reports clean for a default tool-mode install rather than flagging every one as drifted; the doctor, hostile-filesystem lifecycle, and shared-agents-dir tests that a fresh default install newly reaches all pass.

## Notes

Making `_scaffold_precommit` mode-aware means a default install (tool mode) now emits `uvx` hook entries, which the previously dependency-pinned `collect_precommit_state` flagged as non-canonical, breaking `spec doctor` for every default install. The minimal call-site fix - having `collect_precommit_state` derive its expected entries from the resolved mode - was applied in `collectors.py` to keep the doctor honest without leaving the suite red. This is the essential slice of the diagnosis phase's `collect_precommit_state` update pulled forward; the dedicated mode-mismatch signal, resolver rewording, and the `collect_mode_mismatch_state` collector remain for the diagnosis phase. The module-level `CANONICAL_HOOK_ENTRIES` constant is retained for any other importer. One unrelated pre-existing failure, `test_upgrade_reseeds_builtins`, fails identically on the prior commit (a rules-tree layout discrepancy, not a mode issue) and was left untouched.
