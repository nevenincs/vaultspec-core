---
tags:
  - '#exec'
  - '#adr-topic-infix'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S05'
related:
  - "[[2026-07-27-adr-topic-infix-plan]]"
---

# Cover CLI creation of two same-day topic-infixed ADRs

## Scope

- `tests/test_commands.py`

## Description

- Invoke the public `vault add adr` command in a real installed workspace.
- Create two same-day ADRs with distinct normalized topics.
- Assert duplicate-topic rejection and the exact persisted filenames.

## Outcome

The CLI regression proves the issue workflow without bypassing parsing, validation,
or file creation. The duplicate call exits nonzero and preserves both created ADRs.

## Notes

`tests/test_commands.py::test_vault_add_creates_distinct_same_day_topic_infixed_adrs`
passed.
