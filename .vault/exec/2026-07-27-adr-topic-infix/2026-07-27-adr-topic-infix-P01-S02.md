---
tags:
  - '#exec'
  - '#adr-topic-infix'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:a6c018fe73f6b59545266688cc7592d4689ecba01baea4e553d340143c01c9b9'
step_id: 'S02'
related:
  - "[[2026-07-27-adr-topic-infix-plan]]"
---

# Align CLI topic validation and help text with ADR admission

## Scope

- `src/vaultspec_core/cli/vault_cmd.py`

## Description

- Add ADR to the CLI topic-infix help contract.
- Admit ADRs before normalizing the optional topic value.
- Keep unsupported plan and execution-record types rejected.

## Outcome

CLI callers can create an ADR with a topic and receive the same normalized value
that the shared creator accepts. The CLI remains explicit about the four supported
document types.

## Notes

No command routing changed; the CLI continues to delegate filename construction to
the shared creator.
