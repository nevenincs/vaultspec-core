---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S18'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Thread the package parameter through the doctor's mode-mismatch and version-floor rows so core's own row reads core's own map entry

## Scope

- `src/vaultspec_core/core/diagnosis/diagnosis.py`

## Description

- Add a `PackageModeDiagnosis` dataclass and a `packages` map field to
  `WorkspaceDiagnosis`, one entry per distribution declared in the shared
  workspace map, carrying that package's declared mode, mode-mismatch signal,
  and floor state.
- Populate the map in `diagnose` from the declared-packages read, collecting
  each package's mode-mismatch and floor against its own entry, while keeping
  the top-level core signals as the resolver's own view.
- Re-export `PackageModeDiagnosis` from the diagnosis package.
- Render one install-mode doctor row per declared package, labeling the honest
  declared mode (dev stays dev), and a version-floor row per package only when
  its running version is below its declared floor; fall back to the single
  legacy row when no packages map exists.
- Weigh the doctor exit code per declared package: any package's mismatch is a
  warning and any package's floor violation is an error, with the legacy
  single-view fallback preserved.

## Outcome

A workspace declaring both core and a companion package now renders an
install-mode row per package (each labeling its own declared mode) plus a
per-package floor row when violated, verified against a mixed
core-dev/rag-tool-with-floor configuration. Core's own top-level signals and the
resolver's plans are unchanged. The doctor, collector, and signal suites (125
tests across the runs) pass and `ty check` is clean; the doctor `--json` payload
gains the `packages` map without breaking existing consumers.

## Notes

The per-package rows are rendered in `src/vaultspec_core/cli/spec_cmd.py` and the
exit-code weighting there; the diagnosis data model lives in
`src/vaultspec_core/core/diagnosis/diagnosis.py`. Both were touched to thread the
package parameter end to end through the doctor.
