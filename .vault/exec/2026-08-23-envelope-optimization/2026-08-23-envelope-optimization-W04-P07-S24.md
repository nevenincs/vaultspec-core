---
tags:
  - '#exec'
  - '#envelope-optimization'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:d060aa05c4a325610745e9966d12be8184585364c7485e7738457af4e0a1c6d7'
step_id: 'S24'
related:
  - "[[2026-08-23-envelope-optimization-plan]]"
---

# Window the feature listing, which returns every feature unbounded

## Scope

- `src/vaultspec_core/cli/vault_feature_cmd.py`

## Description

- Apply the shared window to the feature listing before it is serialised.
- Add limit and offset options, and emit the window fields beside the rows.
- Window unconditionally, so an absent limit means the default rather than no cap.
- Bump the payload contract to its second version, since the shape gained fields.

## Outcome

Measured at 10,476 documents, where the vault carries 660 features: the listing fell from
111,383 bytes to 8,716, inside the budget its tier is assigned. A caller asking for two
hundred rows gets 34,459 bytes, and paging past the first window works.

## Notes

This surface was not among the plan's original Steps, and it was not one of the exit
criteria the decision record names. It surfaced from re-measuring the whole command
surface at the final commit rather than trusting figures taken earlier in the work, and
it was the only remaining payload with no ceiling.

Feature count grows with the corpus, so by the decision record's own rule - that
unboundedness is the defect rather than any particular size - the listing was
non-conformant however small it happened to look on a given vault. Leaving it while
declaring the campaign complete would have repeated the defect the campaign exists to
remove: a marker claiming more than it knows.

The first implementation made the window conditional, so an absent limit still returned
everything and the default remained unbounded. That is the wrong default for the same
reason: a caller who names no limit is the caller least likely to have thought about the
size of the answer.
