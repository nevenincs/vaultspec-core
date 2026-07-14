---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S17'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Add a package parameter to collect_mode_mismatch_state and collect_version_floor_state, reading the package's own declared mode and floor against its own observed artifact shape

## Scope

- `src/vaultspec_core/core/diagnosis/collectors.py`

## Description

- Add a package parameter to `collect_mode_mismatch_state`, reading the named
  package's own map entry, and fix the false-mismatch defect: compare the
  declared mode through render_mode against the observed shapes, so a
  declared-`dev` package (which renders byte-identically to `dependency`) reads
  coherent instead of always flagging mismatch.
- Add a package parameter to `collect_version_floor_state`, testing the named
  package's own installed version against its own declared floor, delegating to
  the shared `evaluate_version_floor` comparator.
- Thread the package parameter through the observed-shape helpers: pre-commit
  hooks are core's own artifact, so `_observed_precommit_mode` observes nothing
  for a non-core package; `_observed_mcp_mode` reads the named package's server
  entry, recovers its module from the deployed args, and matches through the
  shared `render_launch_for_mode` comparator so it works for any package's module
  without a second launch table.
- Give `evaluate_version_floor` a package parameter reading that package's own
  `minimum_version` entry, keeping the single shared floor comparator the
  resolver's refuse-and-tell path and the doctor both use.

## Outcome

`collect_mode_mismatch_state` now returns CLEAN for a `dev` declaration against
dependency-shaped artifacts (the reproduced P01 false-mismatch), while a genuine
tool-versus-dependency divergence still flags MISMATCH. Both collectors and the
floor comparator resolve per package, defaulting to core so every existing call
site is byte-transparent. The collector, migration-trigger, signal, resolver,
and workspace-mode suites (239 tests across the runs) pass and `ty check` is
clean.

## Notes

`evaluate_version_floor` lives in `src/vaultspec_core/core/workspace_mode.py`;
its package parameter is the shared-comparator companion to this step's
collector change and was made here to avoid introducing a second, divergent
floor comparator in the collector.
