---
tags:
  - '#exec'
  - '#plan-mutation-concurrency'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:b222625429619db0079ccef046a0a080cefed0345aa751fde3cbbee8ed61de31'
step_id: 'S02'
related:
  - "[[2026-08-13-plan-mutation-concurrency-plan]]"
---

# Converge CLI plan mutation commands on the shared transaction owner

## Scope

- `src/vaultspec_core/cli plan command modules`

## Description

- Add one typed CLI decorator around the full handler callback.
- Apply the transaction boundary to all step, phase, wave, epic-edit, and tier mutation verbs.
- Preserve non-mutating status, query, show, and trailer paths unchanged.

## Outcome

All structural CLI mutation verbs now read, mutate, persist, and verify within the
shared per-document lock. The focused 22-test plan E2E lane, Ruff, and Ty pass.

## Notes

The wrapper binds the original handler signature, so direct Python calls and Typer
keyword invocation derive the same path and dry-run behavior.
