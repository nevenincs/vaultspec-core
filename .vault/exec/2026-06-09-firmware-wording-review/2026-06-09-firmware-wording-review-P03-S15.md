---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
step_id: S15
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# add the missing vault add flags --tier, --step, --all-steps, and --no-hints to the vault add section (D6)

## Scope

- `src/vaultspec_core/builtins/reference/cli.md`

## Description

- Verify the live flag surface with `vault add --help` (read-only): the help lists
  `--no-hints` (suppress next-step advisory hints), `--tier` (plan tier `L1`..`L4`,
  default `L1`, ignored for non-plan document types whose templates carry no tier
  field), `--step` (canonical ID or display path of step to scaffold), and
  `--all-steps` (scaffold execution records for all steps in parent plan)
- Append four rows to the `vault add` options table in the bundled CLI reference,
  mirroring the live help order after `--json`: `--no-hints`, `--tier TIER` (default
  `L1`), `--step ID`, `--all-steps` (D6)
- Run mdformat --wrap 88 on the edited file

## Outcome

The `vault add` section of the bundled CLI reference now documents every flag the live
0.1.26 surface exposes, closing the first of the five `reference/cli.md` lag items the
research identified. Sibling rules that reference `--tier` and `--no-hints` (the
dry-run-discipline rule's worked example, the archive-discipline rule) no longer depend
on undocumented flags. Defaults and descriptions were derived from the `--help` output,
not the sibling prose.

## Notes

The `--help` output marks `--feature` as optional (no required marker) while the
existing table row says required; that pre-existing row is outside this Step's add-only
scope and was left untouched. No mutating command was run during verification.
