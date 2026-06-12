---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S88
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# replace the British spellings serialiser, behaviour, and centre with American forms (D15)

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec-plan-editing-discipline.builtin.md`

## Description

- Verify the file for the inventoried British spellings serialiser, behaviour, and
  centre before editing
- Confirm the only remaining matches are the two backticked `--canonicalise` tokens,
  which name the literal CLI flag and stay by decision
- Confirm against the live CLI that the flag is spelled `--canonicalise` (help output
  of the plan step verbs)
- Trace the resolution to the P02.S14 rewrite, which replaced the rule body wholesale
  with American "serializer" prose

## Outcome

Already resolved by P02.S14 (commit acbfb46): the rule shortening rewrote the body
with American spellings, so no edit is needed. Grep evidence: a search for
`serialiser`, `behaviour`, and `centre` across the file returns zero matches; the
only `canonicalise` occurrences are the two backticked `--canonicalise` CLI-flag
references, which the sweep deliberately preserves because they name the shipped flag
verbatim. The commit for this Step carries the record and plan state only.

## Notes

No builtin file changed in this Step.
