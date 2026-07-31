---
tags:
  - '#exec'
  - '#vault-scale-performance'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
body_hash: 'sha256:ece6d0cc0ba6c1376ce3375122c238118878a8f79e0381af061cf53f7baa1906'
step_id: 'S17'
related:
  - "[[2026-07-27-vault-scale-performance-plan]]"
---

# cap the check report phase with marked truncation and aggregates and a fixed console geometry

## Scope

- `src/vaultspec_core/cli/vault_cmd.py`

## Description

- Cap rendered findings at fifty per check with a marked truncation
  line pointing at the JSON surface; pin the shared console width at
  construction so geometry is queried once per run.

## Outcome

Human check output is bounded on large corpora; summary counts stay
complete and the JSON contract is uncapped and unchanged.

## Notes

Small corpora below the cap render byte-identically.
