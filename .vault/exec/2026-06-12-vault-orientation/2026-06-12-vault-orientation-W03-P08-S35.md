---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-13'
step_id: S35
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# describe the orientation surface and the modified stamp in the framework manual

## Scope

- `docs/framework.md`

## Description

- Added "Orientation - the zeroth move" subsection to `docs/framework.md` ahead of the
  "Research" section: `vaultspec-core vault status` rollup mode, targeted grounding-trace
  mode, and the distinction from auditing - woven into the existing narrative structure.
- Added `modified:` stamp passage to the "Managing vault records" section: CLI-owned
  lifecycle, scaffold-time stamping, automatic refresh on every mutating verb, the
  check-fix reconciliation path, and its role as the recency source for the status rollup.
- Fixed two bare `` `vault status` `` prose references to the full
  `vaultspec-core vault status` form required by the language-contract guard.
- Ran `uv run --no-sync mdformat --wrap 88 docs/framework.md`.

## Outcome

All 14 guard tests pass: `test_cli_language_contract`, `test_cli_reference_drift`, and
`test_cli_handbook_drift`.

## Notes

The language-contract test scans `docs/framework.md` as part of all doc paths; bare
subcommand references without the `vaultspec-core` prefix fail the check. Both were
caught and corrected before the final guard run.
