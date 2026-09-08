---
tags:
  - '#adr'
  - '#framework-reword'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:70e2e1021daeb62b171227a43f0a08814bb63d374bd914b7598552b9d741ce86'
related:
  - "[[2026-09-08-framework-reword-research]]"
---

# `framework-reword` adr: `proportional pipeline routing and decision coverage` | (**status:** `accepted`)

## Problem Statement

Vaultspec needs one routing contract that preserves durable decisions and execution continuity without manufacturing decisions to satisfy duration or delegation rules. `2026-09-08-framework-reword-research` grounds this decision. The user approved the proposed resolutions and four major revisions on 2026-09-08 and requested an independent Astra review of the cohesive framework.

## Considerations

- Decision need and planning need are independent; `2026-09-08-framework-reword-research`.
- Existing accepted decisions remain reusable authority within their settled constraints; `2026-09-08-framework-reword-research`.
- Evidence, approval state, execution scope, and review must remain consistent across instruction and executable surfaces; `2026-09-08-framework-reword-research`.

## Considered options

- Retain horizon-mandated ADRs: rejected because decision-free work would require a fictitious decision.
- Separate decision coverage from planning need: selected; plans preserve scope and continuity while ADRs preserve costly commitments.
- Make the lifecycle advisory: rejected because approval and durable recovery remain necessary.
- Encode exhaustive routing classifications: rejected because a short coverage test and explicit scope suffice.

## Constraints

A costly decision establishes or changes a commitment whose reversal requires coordinated migration, compatibility work, or material operational change. Boundaries, persisted schemas, protocols, public interfaces, and dependency strategy are examples; routine choices within settled constraints are execution. Discover governing decisions across features. Reuse accepted ADRs unchanged when their constraints cover the work; amend a refinement, supersede a reversal, and create a separate ADR for a distinct costly decision. Concurrent plans may share an ADR when execution scopes, ownership, and dependencies are compatible.

An approved plan may have no governing ADR when discovery finds no costly decision involved. Its Description records that coverage assessment and scope; no placeholder ADR or evidence record is required merely for planning. Existing governing ADRs must still be linked. Research, Reference, or an Audit with sufficient evidence may ground a decision. Missing evidence is gathered in the appropriate record. Plans inherit ADR evidence transitively; direct supporting links remain optional.

Approval is scoped user authorization, including explicit advance authorization. Persist its basis; never infer it from elapsed time or record status alone. Routine corrections within approved intent do not need renewed permission; changed scope, costly commitments, or external authority do. Preserve accepted ADR content while an amendment is pending, presenting a proposed revision separately for approval before replacing it. A successor must be accepted before supersession retires the old decision. Historical plan links retain their historical meaning; active execution must have accepted decision coverage.

## Implementation

The always-on system owns routing, coverage, approval, and review policy. Record rules own artifact boundaries; templates own syntax and tier structure; skills and personas implement those contracts without independent policy variants. Relevant creation, validation, repair, and ADR transition code must agree. Checks verify explicit links and status, not infer semantic approval or invent authority by selecting a same-feature record.

Use a plan when scope or progress must survive sessions or handoff, or coordination needs durable sequencing. File counts and parallel workers alone do not force a tier. L1 is a flat sequence of cohesive, verifiable revisions; add containers only when they clarify coordination and dependencies. Expected file creation and routine path corrections are not blockers. Parallel assignments may be Steps at L1 or containers at higher tiers, with isolated writes and coordinated shared metadata and commits.

Formal review is for planned work: review the integrated changed behavior against the plan and its governing decisions at Phase close where Phases exist, plan close, and handoff. Coincident gates share a review. A Step closes on its verification. L1 requires no invented Phase. Review the complete affected workflow across rules, skills, personas, templates, and executable contracts, not each document as a separate approval gate. Planless review stays in the reply. In-scope corrective findings are covered by the approved work; findings requiring new scope or decisions are separately authorized.

## Rationale

Separating decision coverage from execution effort resolves the contradictory routes established in `2026-09-08-framework-reword-research` while retaining explicit authority for costly commitments. Transitive evidence avoids duplicated required links. Scoped authorization and cohesive Steps allow routine implementation judgment without silently broadening the user's request.

## Consequences

Decision-free plans become valid, accepted decisions remain reusable, and short parallel work does not require external project tracking. Validators must distinguish draft, active, and historical use rather than treating every ADR-shaped link as authority. Semantic coverage remains an agent responsibility; regression scenarios and independent cohesive review complement structural checks. Existing historical records and optional evidence links remain valid; no bulk rewriting of the vault is required.
