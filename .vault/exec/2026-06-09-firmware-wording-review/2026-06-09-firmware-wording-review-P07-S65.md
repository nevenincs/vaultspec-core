---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S65
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# move the instructional boilerplate and the file1 and file2 placeholders inside comment blocks so sanitize strips them (D14)

## Scope

- `src/vaultspec_core/builtins/templates/exec-summary.md`

## Description

- Move the "Brief summary of overall progress" instructional sentence and the
  Modified/Created bullets carrying the file1 and file2 placeholders into a single
  hint comment below the H1
- Format the template with mdformat at wrap 88

## Outcome

The exec-summary template body no longer renders instructional prose or the
undefined file1/file2 placeholders into persisted documents: both now live inside an
HTML comment that `vaultspec-core vault sanitize annotations` strips and that the
hydration unresolved-placeholder scan ignores. The H1 and the Description section
hint are unchanged. Template annotation tests pass.

## Notes

None.
