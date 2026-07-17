---
tags:
  - '#exec'
  - '#reference-topic-infix'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S04'
related:
  - "[[2026-07-16-reference-topic-infix-plan]]"
---

# Add unit tests covering infixed filenames per admitting type, omitted-topic fallback, non-admitting-type error, normalization, and collision behavior

## Scope

- `src/vaultspec_core tests`

## Description

- Add scaffolder tests (infixed filename per admitting type, omitted-topic
  fallback, non-admitting `ValueError`, coexisting topics, duplicate-topic
  collision), CLI tests (success, type guard, non-kebab rejection), and MCP
  batch tests (second same-day reference, per-item type failure).

## Outcome

38 + 8 tests green across the three surfaces (suites run separately per the
known cross-conftest interaction). Modified:
`src/vaultspec_core/vaultcore/tests/test_hydration.py`,
`src/vaultspec_core/tests/cli/test_vault_cli.py`,
`tests/unit/mcp_server/test_create_tool.py`.

## Notes

None.
