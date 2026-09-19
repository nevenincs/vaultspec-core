---
tags:
  - '#adr'
  - '#cli-restructure'
date: '2026-03-23'
modified: '2026-09-19'
body_hash: 'sha256:e88e363bb1b17f826ddd3cafd07614dc7f4d501c967853f2fa815e64dd185dbe'
related:
  - '[[2026-03-23-cli-restructure-research]]'
---

# `cli-restructure` adr: `cli restructure` | (**status:** `deprecated`)

## Problem Statement

This record was scaffolded on 2026-03-23 and never authored. Every section below
retained its template placeholder text, so the record states no problem, weighs no
options, and commits to no decision. It is deprecated rather than superseded: nothing
was ever decided here for a successor to replace.

## Considerations

The scaffold carried an `accepted` status token, which made an empty record read as a
ratified decision to both a human reader and any status-driven tooling. Its grounding
research record, `2026-03-23-cli-restructure-research`, is an unfilled scaffold of the same date.

## Constraints

Deprecation changes only this record's status and states what it contains. It asserts
nothing about the work the feature tag covers, which is evidenced by that feature's
execution records where they exist.

## Implementation

None. No decision is recorded, so nothing governs and nothing rolls out.

## Rationale

The CLI structure this record names is governed by real, fully authored decisions -
`2026-03-05-cli-engine-typer-adr` and `2026-03-05-cli-path-resolution-adr` - which
predate it and carry their own evidence. This scaffold adds nothing they do not
already settle.

## Consequences

Good: the corpus no longer presents an empty scaffold as an accepted decision.

Bad: whatever reasoning was intended on 2026-03-23 is not recoverable from this record.

Neutral: if the underlying decision still needs recording, it is authored as a new ADR
with its own evidence rather than by filling this one in retrospectively.
