---
tags:
  - '#exec'
  - '#uniform-rename'
date: '2026-06-26'
modified: '2026-06-27'
step_id: 'S06'
related:
  - "[[2026-06-26-uniform-rename-plan]]"
---

# Implement the anchored date-keyed feature-segment path transform for docs, exec folder, and exec records

## Scope

- `src/vaultspec_core/vaultcore/query.py`

## Description

- Add an anchored authored-document filename transform keyed on the date prefix and the source-feature boundary so only the feature segment is swapped and a prefix collision cannot over-match.
- Add an exec-folder date matcher that recognizes the date-and-feature folder name and returns the parent plan date.
- Add an exec-record filename transform that holds the plan-date prefix fixed and replaces only the source-feature token, preserving any step, phase, or summary suffix verbatim.

## Outcome

- Three small pure transforms map every binding filename surface to its renamed form and return a sentinel when the input does not carry the expected feature segment, letting the caller refuse non-conformant inputs rather than half-rename them.

## Notes

- The authored transform deliberately preserves any suffix after the feature segment rather than enumerating document types, so audit filenames carrying a narrative topic infix between the feature and the type are renamed correctly. This is a refinement over a type-enumerated pattern, which would silently skip topic-bearing audits and leave them as drift.
