---
tags:
  - '#exec'
  - '#rename-convergence'
date: '2026-06-27'
modified: '2026-06-27'
step_id: 'S18'
related:
  - "[[2026-06-27-rename-convergence-plan]]"
---

# Regenerate the CLI reference, re-seed the workspace, and run the full unit gate green

## Scope

- `src/vaultspec_core/builtins/reference/cli.md`

## Description

- Regenerate the managed regions of the bundled CLI reference and the published CLI doc so they carry the new command.
- Re-seed the workspace so the dogfood reference matches the regenerated bundle.
- Run formatting, linting, and type checks on the changed files and the full unit gate, and run the vault audit on the repository.

## Outcome

- Reference regeneration updated the bundled `cli.md` and the published `CLI.md`; re-seeding reported one updated file, the dogfood reference copy.
- Formatting, lint, and type checks are clean on every changed file.
- The full unit gate passed with 1543 tests, the 1526 baseline plus the 17 new checker tests, with no regressions.
- The repository audit reports the new check clean, with no new findings beyond a pre-existing unrelated plan-references warning.

## Notes

- The check-order stability test required updating its expected ordered check list to include the new check after the feature-completeness check. This reflects the new wiring and is derived from the specification, not copied from a failing run.
