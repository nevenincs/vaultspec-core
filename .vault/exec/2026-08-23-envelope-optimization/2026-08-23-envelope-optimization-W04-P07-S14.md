---
tags:
  - '#exec'
  - '#envelope-optimization'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:558cd24c9884a21bf7705e1834fd372c77d72f10dc73685b11616e0835bbcb9d'
step_id: 'S14'
related:
  - "[[2026-08-23-envelope-optimization-plan]]"
---

# Add limit and offset to document listing, make paths vault-relative and drop derivable fields

## Scope

- `src/vaultspec_core/vaultcore/query_listing.py`

## Description

- Apply a window to the document listing before the format branch.
- Add limit and offset options.
- Drop the fields a caller can derive and make paths vault-relative.

## Outcome

A full-corpus dump with no cap: 5,934,666 bytes at 10,476 documents, where the only narrowing available was an exact feature or date. It is the most obvious discovery call an agent makes. It now returns 7,581 bytes.

Rows drop what the caller can derive - the stem of the path, and tags restating the type and feature already present as fields - and paths are emitted relative to the vault rather than repeating the absolute prefix on every row.

## Notes

One trap is worth recording: the dataclass conversion leaves a path as a path object, so guarding the prefix strip on a string type silently skipped every row while the serialiser shipped the absolute path anyway. The projection looked correct and did nothing.
