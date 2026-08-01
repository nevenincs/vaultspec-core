---
tags:
  - '#exec'
  - '#mcp-read-only'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:4829946e273e8e6ffc9dbc80f794e7cd56f4f7b2af783bba93df6e385a81d6b5'
step_id: 'S01'
related:
  - "[[2026-08-01-mcp-read-only-plan]]"
---

# `S01` execution record

## Description

- Add the `--read-only` Typer launch option.
- Thread the mode through server construction and the stdio serving entry point.
- Keep the default launch mode and instructions unchanged.

## Outcome

`vaultspec-mcp --read-only` constructs the restricted server mode; an ordinary launch retains the complete nine-tool surface.

## Notes

No service lifecycle change was made.
