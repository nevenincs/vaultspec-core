---
tags:
  - '#exec'
  - '#markdown-feature-scope'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
step_id: 'S03'
related:
  - "[[2026-07-27-markdown-feature-scope-plan]]"
---

# Add a stale-workspace CLI regression for feature-scoped Markdown repair

## Scope

- `src/vaultspec_core/tests/cli/test_migration_triggers.py`

## Description

- Provision an installed workspace and create selected alpha and unselected beta research records.
- Rewind the real manifest to the modified-stamp migration boundary.
- Invoke the actual feature-scoped Markdown fixer and compare raw unselected bytes.

## Outcome

The regression failed before the implementation because beta received a `modified:` stamp, then passed after the scoped scanner change while alpha was repaired.

## Notes

No mocks, patches, or synthetic migration registry were used.
