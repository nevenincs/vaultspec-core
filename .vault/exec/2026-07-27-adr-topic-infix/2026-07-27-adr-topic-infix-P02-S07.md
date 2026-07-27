---
tags:
  - '#exec'
  - '#adr-topic-infix'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S07'
related:
  - "[[2026-07-27-adr-topic-infix-plan]]"
---

# Revise the owned topic-infix rule and regenerate its published reference

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`

## Description

- Revise the canonical rule to admit ADR topic infixes.
- Update the hand-authored CLI reference option description.
- Sync the managed `.vaultspec` rule and reference copies.

## Outcome

The source and installed framework documentation now describe the same four-type
contract as the CLI, MCP, and shared creator. The generated CLI reference check is
clean.

## Notes

The managed upgrade changed only `reference/cli.md` and `rules/vaultspec.builtin.md`.
