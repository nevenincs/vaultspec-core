---
tags:
  - '#adr'
  - '#roadmap'
date: '2026-03-23'
modified: '2026-09-19'
body_hash: 'sha256:c7920867cf21d3ebd042cdc5325e3e75a322564e04f5abb7c8c4d720e4d90fbd'
related:
  - '[[2026-03-23-roadmap-research]]'
---

# `roadmap` adr: `roadmap` | (**status:** `deprecated`)

## Problem Statement

This record was scaffolded on 2026-03-23 and never authored. Every section below
retained its template placeholder text, so the record states no problem, weighs no
options, and commits to no decision. It is deprecated rather than superseded: nothing
was ever decided here for a successor to replace.

## Considerations

The scaffold carried an `accepted` status token, which made an empty record read as a
ratified decision to both a human reader and any status-driven tooling. Its grounding
research record, `2026-03-23-roadmap-research`, is an unfilled scaffold of the same date.

## Constraints

Deprecation changes only this record's status and states what it contains. It asserts
nothing about the work the feature tag covers, which is evidenced by that feature's
execution records where they exist.

## Implementation

None. No decision is recorded, so nothing governs and nothing rolls out.

## Rationale

No governing decision can be reconstructed from an empty record without inventing
one. Authoring content now would fabricate a decision history rather than record it,
so the honest terminal state is deprecation.

## Consequences

Good: the corpus no longer presents an empty scaffold as an accepted decision.

Bad: whatever reasoning was intended on 2026-03-23 is not recoverable from this record.

Neutral: if the underlying decision still needs recording, it is authored as a new ADR
with its own evidence rather than by filling this one in retrospectively.
