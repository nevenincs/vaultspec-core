---
tags:
  - '#adr'
  - '#framework-reword'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:9fa759df6ca069ce5d6f1e462b5bf88807c02fb2da0ac4c0a06c177c392103f8'
related:
  - "[[2026-09-08-framework-reword-research]]"
---

# `framework-reword` adr: `proportional pipeline routing and decision coverage` | (**status:** `proposed`)

## Problem Statement

Vaultspec needs one authoritative routing contract that preserves durable decisions and
multi-session continuity without requiring lifecycle artifacts merely because work is
large, delegated, or mechanically broad. The current bundled language cannot express
decision-free planned work coherently and does not state when an accepted ADR may govern
a later plan. `2026-09-08-framework-reword-research` establishes the conflicting
contracts and the independently converged interpretation. This proposed record reserves
the decision boundary; it does not yet select the policy.

## Considerations

- Decision records must remain about decisions, not become paperwork for duration or file
  count; `2026-09-08-framework-reword-research`.
- Plans need durable authority and scope even when they reuse a prior decision or execute
  work with no new architectural choice; `2026-09-08-framework-reword-research`.
- Direct work must still discover governing decisions without turning discovery into a
  persisted Research or Reference mandate; `2026-09-08-framework-reword-research`.
- System text, rules, skills, personas, templates, checkers, and semantic tests must not
  encode competing lifecycle contracts; `2026-09-08-framework-reword-research`.
- Formal review must remain proportional and must not be selected for planless work;
  `2026-09-08-framework-reword-research`.

## Considered options

- **Retain horizon-mandated ADR creation and clarify edge cases.** Preserves the current
  artifact chain but still requires a decision record when no decision exists.
- **Separate decision coverage from planning need.** Require a new ADR only for a new or
  changed costly-to-reverse decision; reuse an accepted ADR when it covers the work; allow
  proportionate planning without manufacturing a decision. This matches the converged
  reading but still requires precise coverage, approval, and concurrency rules.
- **Make the entire lifecycle advisory.** Maximizes agent discretion but weakens durable
  approval, traceability, and cross-session recovery where those properties are needed.
- **Encode a full routing state machine in prose and checks.** Reduces interpretation drift
  but risks replacing one rigid harness with another if classifications are exhaustive.

No option is selected in this placeholder.

## Constraints

- One ADR records one decision; evidence stays in its grounding record.
- Existing accepted ADRs must not be duplicated only because execution uses a new plan.
- No source, test, or generated provider copy changes before this ADR is completed and
  approved.
- Canonical changes land under `src/vaultspec_core/builtins/` and propagate through the
  owning synchronization machinery.
- The decision must explicitly settle Audit grounding, plan-link shape, accepted-status
  enforcement, amendment and supersession ordering, cross-feature reuse, short parallel
  work, and tier-aware review cadence.

## Implementation

Pending. Complete this section only after the routing, grounding, linkage, approval, and
review choices above are selected.

## Rationale

Pending decision. No option is favored by this placeholder beyond the evidence boundaries
recorded in `2026-09-08-framework-reword-research`.

## Consequences

Pending. Consequences will be evaluated after the decision defines what becomes flexible,
what remains mandatory, and which surface owns each contract.
