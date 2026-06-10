---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
step_id: S18
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# add the plan-verb --phase, --wave, --dry-run, and --canonicalise flags to the plan subcommand sections (D6)

## Scope

- `src/vaultspec_core/builtins/reference/cli.md`

## Description

- Verify the live flag surfaces with `--help` (read-only) on
  `vault plan step add` (`--phase`: parent Phase id, required at L2+, omitted at L1),
  `vault plan phase add` (`--wave`: parent Wave id, L3+ only), `vault plan wave add`,
  and `vault plan tier promote`
- Confirm the universality of `--dry-run` (preview changes without writing to disk)
  and `--canonicalise` (strip unknown prose blocks during serialization) by also
  checking `vault plan step check`, `vault plan epic intent edit`, and
  `vault plan tier demote` help output
- Add a standalone sentence to the `vault plan` section stating every mutating plan
  verb accepts `--dry-run` and `--canonicalise`, noting `--canonicalise` is off by
  default so authored prose is preserved (D6)
- Add `--phase` to the Step `add` flag prose and `--wave` to the Phase `add` flag
  prose, with their tier conditions from the help text (D6)
- Run mdformat --wrap 88 on the edited file

## Outcome

The bundled CLI reference's `vault plan` section now documents the parent-container
flags and the universal preview/canonicalise pair. The plan-editing-discipline rule,
shortened in P02 on the preserved-prose premise, and the dry-run-discipline rule's
preview contract now both resolve against the bundled reference. The off-by-default
note on `--canonicalise` records the prose-preservation default that P02.S13 confirmed
live.

## Notes

The `vault plan tier promote` help also exposes a `--target TIER` option (target tier
`L2`/`L3`/`L4`, defaults to one tier above current) that the bundled reference does not
document; it is outside this Step's four-flag scope and is left for the P09.S125
regeneration follow-up issue to capture.
