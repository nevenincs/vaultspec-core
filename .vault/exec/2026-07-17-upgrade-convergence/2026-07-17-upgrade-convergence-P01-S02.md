---
tags:
  - '#exec'
  - '#upgrade-convergence'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S02'
related:
  - "[[2026-07-17-upgrade-convergence-plan]]"
---

# Add fingerprint-verified refresh to the managed-entry merge with old-to-new narrated warning lines and a refresh item label

## Scope

- `src/vaultspec_core/core/mcps.py`

## Description

- Add `_owned_fingerprints` to read the recorded name-to-fingerprint map
  alongside the existing name-only `_owned_names` reader.
- Add `_launch_repr` to render a config's command and args as one line for
  narration.
- Extend `_apply_server_merge` with a `recorded_fingerprints` parameter and a
  new refresh branch between the force gate and the skip gate: a managed
  entry that differs from its rendered definition but whose on-disk bytes
  still match its recorded fingerprint updates in place, counts through the
  existing `updated` counter with a `[REFRESH]` item label, and appends an
  old-to-new narrated warning line.
- Split the remaining skip path in two: a fingerprint mismatch (hand-edited)
  keeps the existing message; the absence of any recorded fingerprint
  (legacy name-only sidecar) gets its own honest message naming `--force`.
- Thread `recorded_fingerprints` through both callers, `_sync_json_target`
  and `_sync_toml_target`.
- Map the new `[REFRESH]` item label onto `Outcome.UPDATED` in the CLI
  rendering layer alongside the existing `[UPDATE]` mapping.
- Update the module docstring to describe the new convergence behavior.

## Outcome

`_apply_server_merge` now has three distinct outcomes for a managed entry
that differs from its rendered definition: force/force-managed update,
fingerprint-verified refresh (new), and skip-with-warning (split into
hand-edited vs. no-recorded-fingerprint messages). Existing test suites
(`test_mcp_per_package_sync.py`, `test_mcp_provider_files.py`,
`test_install_mode_flip.py`, `test_collectors.py`, 120 tests) pass
unchanged, including the hand-edited-entry-preserved case, confirming the
new refresh path only fires when bytes are provably untouched. `ruff check`
and `ty check` clean on both changed files.

## Notes

None.
