---
tags:
  - '#adr'
  - '#test-quality'
date: '2026-03-23'
modified: '2026-09-19'
body_hash: 'sha256:4ff46a566bafcdd1f29580543a12b5dd21759ea175eb0ca01831822652130cd7'
related:
  - '[[2026-03-23-test-quality-research]]'
---

# `test-quality` adr: `test quality` | (**status:** `deprecated`)

## Problem Statement

This record was scaffolded on 2026-03-23 and never authored. Every section retained its
template placeholder text, so the record states no problem, weighs no options, and
commits to no decision. It is deprecated rather than superseded: nothing was ever
decided here for a successor to replace.

## Considerations

The scaffold carried an `accepted` status token, which made an empty record read as a
ratified decision to both a human reader and any status-driven tooling. Its grounding
research record, `2026-03-23-test-quality-research`, is an unfilled scaffold of the same date.

## Constraints

Deprecation changes only this record's status and states what it contains. It asserts
nothing about the work the feature tag covers, which is evidenced by that feature's
execution records and its plan.

## Implementation

None. No decision is recorded, so nothing governs and nothing rolls out.

## Rationale

Test quality is governed by the core mandates, which forbid tautological tests and
suppression markers outright. The feature's own enforcement pass is evidenced by its
scout reports and audit verdict, not by this empty scaffold.

## Consequences

Good: the corpus no longer presents an empty scaffold as an accepted decision.

Bad: whatever reasoning was intended on 2026-03-23 is not recoverable from this record.

Neutral: if the underlying decision still needs recording, it is authored as a new ADR
with its own evidence rather than by filling this one in retrospectively.
