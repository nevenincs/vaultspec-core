---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-13'
step_id: S32
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# add the zeroth-move orientation paragraph ahead of the pipeline table

## Scope

- `src/vaultspec_core/builtins/system/03-vaultspec.md`

## Description

- Add a three-sentence orient-first paragraph immediately before the
  pipeline-table intro, bolding the defined term and naming
  `vaultspec-core vault status`.
- Frame orientation as the zeroth move: read the in-flight plans, then enter the
  pipeline at the right phase, resuming via `vaultspec-execute` or starting at Research.
- Reflow the file with mdformat at wrap 88.

## Outcome

The always-on system fragment in `src/vaultspec_core/builtins/system/03-vaultspec.md`
now opens the pipeline section with the orientation bootstrap mandate per ADR decision
D8, sequenced after the verb shipped in Wave two so firmware never names an unshipped
verb. The paragraph stays descriptive and points resumers at the existing execute and
research entry points rather than introducing a new phase.

## Notes

None.
