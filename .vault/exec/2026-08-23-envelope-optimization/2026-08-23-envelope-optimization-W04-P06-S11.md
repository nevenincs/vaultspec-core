---
tags:
  - '#exec'
  - '#envelope-optimization'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:77d3eaffb860438acd3aaba6179071ebd8a9ad50ff10009d6418c4ed342446e0'
step_id: 'S11'
related:
  - "[[2026-08-23-envelope-optimization-plan]]"
---

# Evaluate the projection flag before the format flag so a narrowing flag cannot increase the payload

## Scope

- `src/vaultspec_core/cli/vault_cmd.py`

## Description

- Emit the pre-cap total and truncation state on the orientation payload.
- Derive the human remainder line from the true total rather than from the length of the capped list.

## Outcome

The command-line orientation payload fell from 168,377 bytes to 18,459 at 10,476 documents, inside the budget its tier is assigned.

The human surface already capped at ten; it now reports how many were withheld from the same number the machine payload carries, so the two cannot disagree.

## Notes

Before this the only limit the command accepted governed recent documents - the smaller half of the payload - while the larger field it did not reach was uncapped. A flag that narrows the wrong thing is worse than no flag, because a caller reasonably believes it worked.
