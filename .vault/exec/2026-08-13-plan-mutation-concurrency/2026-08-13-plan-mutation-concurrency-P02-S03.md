---
tags:
  - '#exec'
  - '#plan-mutation-concurrency'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:dad2bfac7ebed85b9da3237d7263f720f3b99abd88231e3c12f76aec76a7dc46'
step_id: 'S03'
related:
  - "[[2026-08-13-plan-mutation-concurrency-plan]]"
---

# Converge MCP plan edits and add cross-process lost-update regression coverage

## Scope

- `src/vaultspec_core/mcp_server/tools/plan.py`
- `src/vaultspec_core/tests/plan/test_mutation_concurrency.py`

## Description

- Route MCP plan progress and edit batches through the shared transaction.
- Keep per-item result semantics and one-write batch behavior unchanged.
- Exercise eight simultaneous production CLI processes against one plan.

## Outcome

MCP mutation batches now load and save under the same per-document lock as CLI verbs.
All 11 MCP plan-tool tests pass. The eight-process CLI regression passed twice and
preserved every requested action with gap-free unique identifiers.

## Notes

The first E2E seed attempt used `vault add plan` in an unprovisioned temporary root and
failed before concurrency began. The final test reuses the established deterministic
plan factory and tests only production parser and CLI behavior; no fake, patch, or
monkeypatch is involved.
