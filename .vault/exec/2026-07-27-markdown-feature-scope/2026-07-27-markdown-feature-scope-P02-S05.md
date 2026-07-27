---
tags:
  - '#exec'
  - '#markdown-feature-scope'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
step_id: 'S05'
related:
  - "[[2026-07-27-markdown-feature-scope-plan]]"
---

# Route feature-scoped Markdown checks through the non-migrating scanner mode

## Scope

- `src/vaultspec_core/vaultcore/checks/markdown.py`

## Description

- Select scanner migration behavior from the normalized feature scope.
- Keep unscoped and empty-feature Markdown checks on the default migration path.

## Outcome

A nonempty feature selection now filters before any workspace-wide migration can write unrelated records.

## Notes

The Markdown parser, hygiene transform, feature predicate, and atomic writer were left unchanged.
