---
tags:
  - '#exec'
  - '#vault-scale-performance'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
body_hash: 'sha256:f47d88557d17012ede1552bc98695724df8edb62807a058ae390e157665bc27c'
step_id: 'S10'
related:
  - "[[2026-07-27-vault-scale-performance-plan]]"
---

# route the feature rename integrity check through the shared snapshot

## Scope

- `src/vaultspec_core/vaultcore/checks/feature_rename_integrity.py`

## Description

- Derive exec folder-vs-tag conflicts from the snapshot by grouping
  records under their parent directory; keep the disk walk for the
  standalone verb.

## Outcome

The combined pass compares folders and tags without re-reading any
record.

## Notes

Multi-feature-tagged records compare their sorted-first tag on the
snapshot path; compliant documents are unaffected.
