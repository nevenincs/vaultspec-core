---
tags:
  - '#exec'
  - '#plan-mutation-concurrency'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:64da85e5f7832f0117531bf8e9fd9b932bede4a2b029085e9b998096ed1d139c'
step_id: 'S01'
related:
  - "[[2026-08-13-plan-mutation-concurrency-plan]]"
---

# Implement the typed per-document plan mutation transaction and focused real-behavior tests

## Scope

- `src/vaultspec_core/plan/mutation_transaction.py`
- `src/vaultspec_core/tests/plan/test_mutation_transaction.py`

## Description

- Add a shared callback transaction that derives the ignored per-document sentinel.
- Create lock runtime state only for applying mutations.
- Prove Windows spawn-process serialization with real advisory locks.

## Outcome

The shared transaction blocks a second process until the first callback exits. Focused
pytest, Ruff, Ty, and BasedPyright checks pass with no diagnostics.

## Notes

The first plan Step insertion exposed scaffold annotations as unexpected parsed rows;
the owning verb failed closed and feature-scoped annotation repair resolved it without
touching unrelated vault documents.
