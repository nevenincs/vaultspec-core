---
tags:
  - '#exec'
  - '#upgrade-convergence'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S04'
related:
  - "[[2026-07-17-upgrade-convergence-plan]]"
---

# Cover untouched-entry refresh, hand-edited preservation, name-only legacy sidecar, and companion seam with real-workspace tests

## Scope

- `src/vaultspec_core/tests/cli`

## Description

- Add `TestFingerprintVerifiedRefresh` to `test_mcp_per_package_sync.py`
  with a plain, mode-token-free `probe` definition and five real-workspace
  scenarios: untouched-entry refresh on a plain sync (asserts the
  `[REFRESH]` item and an old-to-new narration), hand-edited-entry
  preservation (fingerprint mismatch, byte-unchanged file, `--force`
  warning), a name-only legacy ownership record (constructed by writing a
  non-string value into the ownership sidecar directly), an external entry
  sharing a declared definition's name (skipped, "externally managed"
  warning), and refresh-then-resync idempotence.
- Add `test_flip_upgrade_refreshes_every_declared_companion` to
  `test_install_mode_flip.py`: a mixed dependency/tool workspace with both
  managed entries hand-altered to fingerprint-mismatch, then core's own
  mode flipped via the committed declaration; asserts a bare
  `install --upgrade` converges both the core and companion entries
  atomically through the widened seam.
- Run the full requested suite plus `ruff check --fix`, `ruff format`, and
  `ty check` on every changed test file.

## Outcome

14 new tests (9 in `test_mcp_per_package_sync.py`, 1 in
`test_install_mode_flip.py`, plus the existing suites re-verified) all
pass with zero mocks, patches, stubs, or skips; every scenario drives a
real `WorkspaceFactory` install/upgrade or a real `mcp_sync` against
on-disk state. `ruff check`, `ruff format`, and `ty check` are clean on
both changed test files. The full CI-matching unit gate
(`pytest src/vaultspec_core -m unit`) was run to confirm no regressions
elsewhere in the suite.

## Notes

The external-entry test needed a source definition sharing the foreign
entry's name to exercise the real "externally managed" skip gate (a
foreign name with no matching source is never visited by the merge loop
at all, so it produced no assertable item in an earlier draft). The
widened-seam test required hand-altering both managed entries with an
env-only field addition (not command/args) so the mode-flip observer
still reads the pre-flip mode correctly while both fingerprints go stale.
