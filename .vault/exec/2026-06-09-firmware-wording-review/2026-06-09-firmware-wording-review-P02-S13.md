---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S13
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# live-confirm plan body-prose preservation by running structural plan verbs against a scratch plan document carrying authored prose sections (D5)

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec-plan-editing-discipline.builtin.md`

## Description

- Scaffold a scratch L2 plan via
  `vault add plan --feature scratch-preservation-check --tier L2` (dry-run preview
  first, then real run) inside this repo's vault
- Author three sentinel prose sentences directly into the Description,
  Parallelization, and Verification sections (SENTINEL-DESC-7391, SENTINEL-PAR-7392,
  SENTINEL-VER-7393), deliberately prose-before-structure, the exact ordering the
  discipline rule forbids
- Run three structural verbs against the prose-bearing plan: `plan phase add`,
  `plan step add --phase P01`, `plan step check S01`
- Grep for the sentinels after each mutation and record the serializer's preservation
  report
- Delete the scratch plan file, confirm no scratch index was created, and verify
  `vault check all` reports all checks passed after cleanup

## Outcome

PASS: prose content is preserved. All three sentinel sentences survived all three
structural mutations byte-for-byte (grep count 3 before and after every verb; sentence
text verbatim). Every mutation reported the preservation explicitly: "Added Phase
`P01`. (Preserved 2 unknown blocks)", "Added Step `P01.S01`. (Preserved 2 unknown
blocks)", "Closed Step `S01`. (Preserved 2 unknown blocks)". The B6 failure mode the
plan-editing discipline rule guards against (silent prose destruction on `step add`)
is gone at 0.1.26, clearing the gate for the S14 rule shortening per decision D5.

## Notes

Two preservation nuances observed, content-safe but position-affecting: the serializer
re-anchors blocks on write (the new Phase block was emitted under the H1 title above
the authored `## Description` section, and the template hint comments were reordered),
and the scaffolded `related: []` frontmatter field was dropped from the empty-related
scratch plan on the first structural write. Prose content survives verbatim; prose
position may shift. `plan step add --help` confirms `--dry-run` ("Preview changes
without writing to disk") and the opt-in `--canonicalise` ("Strip unknown prose
blocks"), so preservation is the default and stripping is explicit opt-in. S14 should
state the content-preserved, position-may-reflow behavior rather than claim full
byte-identity of the document.
