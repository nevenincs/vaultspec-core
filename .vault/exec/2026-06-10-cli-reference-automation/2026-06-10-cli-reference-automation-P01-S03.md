---
tags:
  - '#exec'
  - '#cli-reference-automation'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S03
related:
  - '[[2026-06-10-cli-reference-automation-plan]]'
---

# Correct the vault add --feature required-marker annotation to match live --help and grep the reference for any other stale required-markers (P03 doc gap)

## Scope

- `src/vaultspec_core/builtins/reference/cli.md`

## Description

- Verify the live `vault add --help`: only the `doc_type` argument carries a
  `[required]` marker; the `--feature` option has no required marker and is an
  ordinary optional flag.
- Correct the `vault add --feature` Default column in the bundled reference from
  `required` to `None`, matching the optional-option convention used by the
  neighboring rows.
- Grep the reference for every other `required` token and spot-check each against the
  relevant `--help`.

## Outcome

The `vault add --feature` row now reads `None` in the Default column, matching live
`--help`. The reference's drift guard (`test_cli_reference_drift.py`) still passes (4
passed), and the only remaining `required` token in the file is the accurate prose
describing `vault plan step add --phase` as conditionally required at L2+.

## Notes

- Grep findings: two `required` occurrences in the reference. The first was the
  `vault add --feature` Default cell (the stale marker, now corrected to `None`). The
  second is prose at the `vault plan` section describing `--phase` as "required at L2+,
  omitted at L1"; live `vault plan step add --help` confirms `--action` and `--scope`
  are `[required]` while `--phase` shows the same "required at L2+" conditional, so the
  prose is accurate and was left unchanged.
- Why: the firmware-wording-review code review left a P03 reference-accuracy LOW note
  that the bundled `cli.md` `--feature` marker no longer matched the live CLI surface.
- Origin: the P03 doc gap noted in the `firmware-wording-review` audit, tracked as
  plan Step P01.S03.
