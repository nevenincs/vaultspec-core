---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
step_id: S85
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# fix the Use-Concise-and-Direct label fragment, the i.e.-where-e.g.-is-meant misuse, and the bullet punctuation drift (D15)

## Scope

- `src/vaultspec_core/builtins/system/02-operations.md`

## Description

- Rewrite the broken label fragment "Use **Concise & Direct:** tone." as the
  grammatical sentence "Use a **concise and direct** tone."
- Replace "(i.e. searching the codebase)" with "(e.g., searching the codebase)" in
  the Parallelism bullet, since the parenthetical gives an example rather than a
  restatement
- Move the stray period inside the bold span in the token-efficiency bullet so the
  bold sentence carries its own terminal punctuation
- Supply the missing terminal period on the git-log style bullet ending in "etc.)"
- Format the fragment with mdformat at wrap 88

## Outcome

The operations fragment's tone-label fragment, the i.e./e.g. misuse, and the two
bullet punctuation drifts are resolved per decision D15. Verification grep across the
file for `Concise & Direct` and `i.e. searching` returns zero matches; every bullet
in the touched sections now terminates with a period.

## Notes

None.
