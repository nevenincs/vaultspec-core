---
tags:
  - '#adr'
  - '#cli-target-refactor'
date: '2026-03-23'
modified: '2026-09-19'
body_hash: 'sha256:ef92c5b2c5d34c1132f971792011903c505403b874a64a5ed63f391299206112'
related:
  - '[[2026-03-23-cli-target-refactor-research]]'
---

# `cli-target-refactor` adr: `cli target refactor` | (**status:** `deprecated`)

## Problem Statement

This record was scaffolded on 2026-03-23 and never authored. Every section retained its
template placeholder text, so the record states no problem, weighs no options, and
commits to no decision. It is deprecated rather than superseded: nothing was ever
decided here for a successor to replace.

## Considerations

The scaffold carried an `accepted` status token, which made an empty record read as a
ratified decision to both a human reader and any status-driven tooling. Its grounding
research record, `2026-03-23-cli-target-refactor-research`, is an unfilled scaffold of the same date.

## Constraints

Deprecation changes only this record's status and states what it contains. It asserts
nothing about the work the feature tag covers, which is evidenced by that feature's
execution records and its plan.

## Implementation

None. No decision is recorded, so nothing governs and nothing rolls out.

## Rationale

The refactor this record names is governed by `2026-03-05-cli-engine-typer-adr` and
`2026-03-05-cli-path-resolution-adr`, both fully authored and both linked by the
feature's plan. This scaffold adds nothing they do not already settle.

## Consequences

Good: the corpus no longer presents an empty scaffold as an accepted decision.

Bad: whatever reasoning was intended on 2026-03-23 is not recoverable from this record.

Neutral: if the underlying decision still needs recording, it is authored as a new ADR
with its own evidence rather than by filling this one in retrospectively.
