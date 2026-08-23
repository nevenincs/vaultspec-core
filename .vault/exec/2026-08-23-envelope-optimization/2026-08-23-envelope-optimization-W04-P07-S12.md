---
tags:
  - '#exec'
  - '#envelope-optimization'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:e5a86310c8f7f7f4397dfe1929c29c43eccfdaf1b80aebdba29500f399792d50'
step_id: 'S12'
related:
  - "[[2026-08-23-envelope-optimization-plan]]"
---

# Replace the boolean body flag with a bounded projection and enforce a response byte budget

## Scope

- `src/vaultspec_core/mcp_server/tools/documents.py`

## Description

- Replace the boolean body flag with a three-way projection.
- Carry the full document size and a truncation marker beside an excerpt.
- Refuse whole-document requests above a handful of rows, naming the alternative in the refusal.

## Outcome

The flag inlined complete documents. Twenty rows cost 196,176 bytes at the default limit, on a healthy vault. An excerpt covers the same twenty for 22,389 bytes and states the size it cut from, so a caller knows what it did not receive.

Whole text is now reserved for a caller that has already narrowed, and the refusal names the projection to use instead rather than simply failing.

## Notes

The resource link each row already carries exists precisely so a body does not have to travel inline. Inlining defeated it.
