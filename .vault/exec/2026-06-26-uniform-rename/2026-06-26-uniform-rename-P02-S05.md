---
tags:
  - '#exec'
  - '#uniform-rename'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S05'
related:
  - "[[2026-06-26-uniform-rename-plan]]"
---

# Add feature-tag validation helpers for kebab-case, schema tag form, and reserved DocType names

## Scope

- `src/vaultspec_core/vaultcore/query.py`

## Description

- Add a private validation helper that normalizes both source and target tags with the same strip-and-strip-hash treatment the sibling archive guard uses, then rejects an empty source, an empty target, and an identical source and target.
- Gate the target against the kebab-case grammar and the schema tag form so a malformed target is refused before any work begins.
- Reject a target that collides with a reserved document-type name, since such a feature would be invisible to the feature scanner.
- Confirm the source matches at least one non-archived document by reusing the existing list-documents query, and refuse a target that already owns documents unless force is set.

## Outcome

- A single validation helper returns the normalized source name, the normalized target name, and the source document set, raising a vault-spec error with a clear message at the first failed guard. All guard paths are exercised green by the smoke probe.

## Notes

- Messages mirror the archive empty-tag guard tone. The reserved-name list is derived from the document-type enum so it stays in sync automatically.
