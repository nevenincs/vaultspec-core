---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S35'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Add mode-and-floor rows to the doctor output for the vaultspec-rag entry, reading core's per-package mode-mismatch and version-floor collectors

## Scope

- `src/vaultspec_rag/cli/_service_doctor.py`

## Description

- Add a `_mode_floor_axis(target)` collector to `_service_doctor.py`: it reads
  the `vaultspec-rag` entry from the shared per-package `workspace.json` through
  core `0.1.39`'s package-aware `collect_mode_mismatch_state` and
  `collect_version_floor_state`, both keyed to `vaultspec-rag`, and returns the
  declared mode, the mode-mismatch signal, and the version-floor signal, running,
  and minimum. It returns `None` when no rag entry is declared and swallows any
  collector failure to `None`, so the doctor never crashes and a pre-install run
  shows no provisioning block.
- Add a `_doctor_exit_code(service, mode)` helper folding the daemon and
  provisioning axes into an exit code, error over warn, mirroring core's `spec doctor` weighting: below-floor is an error (exit `2`), a mode mismatch is a
  warning (exit `1`), combined with the existing dead-daemon warning.
- Add `_render_mode_floor_axis(mode)` to print a labelled `Provisioning (vaultspec-rag)` block in the human render, silent when no rag entry is
  declared.
- Thread the axis into `service_doctor`: read it from `Path.cwd()`, add it to the
  JSON envelope under `mode`, render it in human mode, and raise the folded exit
  code.
- Add five real-filesystem, zero-mock tests to `test_server_doctor.py`: a
  no-declaration directory omits the axis and stays exit `0`; a cleanly
  provisioned rag workspace reads mode `clean` and floor `ok` at exit `0`; a
  below-floor declaration exits `2`; a rewritten `.mcp.json` that disagrees with
  the declared mode exits `1`; and the human render carries the labelled block.

## Outcome

`server doctor` now reports rag's own provisioning mode-and-floor axis through
the same core collectors core's own doctor uses, with exit weighting symmetric to
core (below-floor error, mismatch warning). The axis stays silent for a
pre-install or non-workspace directory, preserving the informational exit-`0`
contract. All eight `test_server_doctor.py` tests pass; `ruff`, `ruff format`,
`ty`, and the complexity gate are clean on the changed files. Committed to the
`vaultspec-rag` repository on `feature/install-parity`.

## Notes

The doctor reads its target from `Path.cwd()`, the natural analogue of core's
context target for a command a user runs from the workspace root; rag's `server doctor` has no workspace-target flag and none was added, keeping the parity
surface minimal.
