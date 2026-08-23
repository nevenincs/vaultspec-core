---
tags:
  - '#exec'
  - '#envelope-optimization'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:2d65e6889f694d66c7d4b8548fa719136eedc821808d6badc661dffdd31e01cd'
step_id: 'S19'
related:
  - "[[2026-08-23-envelope-optimization-plan]]"
---

# Emit each repair finding once instead of five times and bound the preview payload

## Scope

- `src/vaultspec_core/cli/_repair_render.py`

## Description

- Emit each repair finding once rather than repeatedly across sections.
- Bound the preview payload.

## Outcome

The preview carried the same findings across several sections and returned every one of them. The dry-run postcheck also re-reported the check phase's findings in full - provable from the code rather than inferred, since it is handed the same results object and a dry run writes nothing.

Measured at 10,476 documents with five percent damage, the phase list fell from 114,747 bytes to 63,774 and the whole payload from 166,140 to 115,167.

## Notes

Counts remain, and an explicit marker says why the findings are absent. An unmarked omission would be indistinguishable from a checker that found nothing, which is the silent-truncation defect in miniature.
