---
tags:
  - "#adr"
  - "#adr-topic-infix"
date: '2026-07-27'
related:
  - "[[2026-07-27-adr-topic-infix-research]]"
  - "[[2026-07-27-adr-topic-infix-reference]]"
  - "[[2026-07-16-reference-topic-infix-adr]]"
supersedes:
  - '2026-07-16-reference-topic-infix-adr'
modified: '2026-07-27'
---

# `adr-topic-infix` adr: `topic-infixed ADR records` | (**status:** `accepted`)

## Problem Statement

A feature can need several same-day, independently searchable decisions while
one plan executes their cluster. The previous topic-infix boundary makes that
valid record shape unrepresentable through the owning creator. The decision is
whether ADRs join the infix admission set or the framework instead changes its
one-decision and plan-cluster guidance. Grounding: `2026-07-27-adr-topic-infix-research`.

## Considerations

- The prior restriction is a standing accepted decision and must be superseded,
  not silently overridden: `2026-07-16-reference-topic-infix-adr`.
- CLI and MCP must converge on the existing single creator and its collision
  authority: `2026-07-27-adr-topic-infix-reference`.
- Plan and exec identifiers have distinct cardinality/derivation constraints;
  this decision does not reopen them.

## Considered options

- **Admit ADR alongside audit, reference, and research (chosen).** Preserves
  one ADR per decision and one feature/plan cluster with the existing mechanism.
- **Keep ADR rejected and revise the guidance.** Rejected: it would retain the
  record-fidelity problem documented in the research.
- **Admit every document type.** Rejected: plan and exec retain their separate
  identifier disciplines without evidence that they need disambiguation.

## Constraints

- Omitted `--topic` behavior and existing collision handling remain unchanged.
- The topic stays normalized at both transport boundaries.
- The built-in rule, installed rule mirror, and generated CLI reference must
  describe the same admission set.
- Existing superseded documents remain valid historical records.

## Implementation

Extend the shared admission set to `adr`, update the two transport guards and
their help/schema wording, revise the owned rule text, and cover same-day
topic-infixed ADR creation, duplicate rejection, and CLI/MCP convergence. The
implementation surface is mapped in `2026-07-27-adr-topic-infix-reference`.

## Rationale

Admitting ADRs is the narrow correction that makes the existing plan-cluster
model and one-decision-per-record convention jointly expressible. It keeps the
single creator and all current identifier safeguards intact, while broader
admission would weaken constraints that do not participate in the issue.
Grounding: `2026-07-27-adr-topic-infix-research` and
`2026-07-27-adr-topic-infix-reference`.

## Consequences

Features may carry several same-day ADRs without splitting their feature tag or
altering dates. The optional flag grows the set of narrative filename forms that
future rename work must support. Existing callers that omit the flag and all
plan/exec creation behavior remain unchanged.
