---
tags:
  - '#exec'
  - '#envelope-optimization'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:e9882fd43cc0cf5cc5100be307883c0b77e3b91d2c9e0c6a4b59eb2ead3029e7'
step_id: 'S15'
related:
  - "[[2026-08-23-envelope-optimization-plan]]"
---

# Cap diagnostics per check on the machine surface and honour the verbosity flag there

## Scope

- `src/vaultspec_core/cli/vault_check_cmd.py`

## Description

- Bound the diagnostics carried by each check on the machine surface.
- Add limit and offset options to every check verb so the cap can be paged past.

## Outcome

Payload size tracks how broken the vault is, so the unbounded form was largest exactly when a caller could least afford it. Measured on a 1,222-document vault: 6,962 bytes clean, 137,323 at five percent of documents damaged, 2,211,057 fully damaged, while the human rendering converged at 69,119 because it had a cap.

At 10,476 documents the aggregate check fell from 653,418 bytes to 88,092, and the ratio between the two surfaces fell from thirty-two times to one and a third.

## Notes

The first version of this shipped a cap with no way past it, which the decision record forbids in as many words: a cap with no way past it converts a saturation failure into a workflow one. An agent remediating a broken vault could see the first fifty findings and had no mechanism to reach the rest, which is worse for that workflow than the unbounded payload it replaced. The window was added in a follow-up. Bounded is only honest when paging exists.
