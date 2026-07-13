---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S63
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# move the uppercase TOPIC, LEVEL, Summary, and DESCRIPTION placeholders into comments using convention-compliant names (D14)

## Scope

- `src/vaultspec_core/builtins/templates/code-review.md`

## Description

- Remove the rendered H2 scaffold carrying the uppercase ad-hoc placeholders and the
  one-line Use comment that repeated them
- Add a FINDINGS FORMAT hint comment teaching the same per-finding heading form with
  lowercase convention-compliant names and the severity vocabulary (critical, sharp,
  minor)
- Format the template with mdformat at wrap 88

## Outcome

No uppercase or convention-violating placeholder survives in the code-review
template body: the per-finding format now lives entirely inside a hint comment that
sanitize strips, using lowercase curly-brace names. A scaffolded code-review
document renders only the H1 plus comments, so no placeholder leaks into persisted
audit documents. Template annotation tests pass.

## Notes

None.
