---
name: vaultspec-adr
description: Record a costly decision, place it within accepted decision coverage, and reconcile affected ADR wording.
---

# ADR (vaultspec-adr)

Records one decision. Apply the system's coverage and approval contract. Reuse accepted
coverage across features; a new task does not require a new ADR.

## Author

- Follow the discovery rule to find governing decisions and their implementation. Read
  the relevant ADRs whole. Choose unchanged reuse, a subsection or amendment to the same
  decision, supersession of a reversal, or a separate distinct decision.
- Reuse sufficient Research, Reference, or Audit evidence. Gather only missing evidence
  through `vaultspec-research` or `vaultspec-code-research`.
- For a new decision, scaffold with `create` (CLI:
  `vaultspec-core vault add adr --feature {feature} --related <evidence-stem>`). Read
  `.vaultspec/templates/adr.md`. Draft directly or delegate to
  `vaultspec-adr-researcher` with the evidence, scope, and affected ADRs.
- State the chosen commitment, scope, binding constraints, rationale, and consequences.
  Distinguish implementation hypotheses from obligations; name reconsideration
  conditions when useful. Keep enough context to understand the ruling and cite detailed
  evidence. An inconclusive spike remains evidence, not an accepted decision.
- Own the affected decision set: return concrete proposed wording for older ADRs whose
  commitments would otherwise conflict, including scoped exceptions or supersession. A
  relation label or a new link alone does not reconcile contradictory text. Follow the
  system's approval contract for applying those changes.

## Jev-assisted placement

Use the existing hosted-search configuration signal from `status`. TypeSafe is opt-in
through `VAULTSPEC_CORE_TYPESAFE_API_KEY`; configured use sends decision text to
TypeSafe. Do not seek credentials or require setup to finish authoring.

- When configured, run one `crossref` pass on the populated draft before offering it
  (CLI: `vaultspec-core vault adr crossref <adr-stem> --json`). For an amendment, pass
  proposed body prose through the tool's `body` argument or CLI `--body-file <path>`;
  this judges it without changing the accepted record. Do not use `apply` for drafts.
- Reuse results supplied for the same draft and relevant corpus state. Recheck only
  materially changed commitments or evidence; do not repeat unchanged reviews.
- Read relevant returned ADRs, especially `supersedes`, `refines`, and `conflicts`
  pairs. Interpret status, scope, exceptions, and ruling history. Confirm useful links
  before adding them through `vaultspec-core vault link add`.
- Missing configuration uses local discovery. On `unavailable`, use the named fallback
  once. Clipped input, unjudged candidates, and a bounded shortlist mean incomplete
  coverage; inspect relevant omitted text. An `ok` result is not approval or proof of no
  conflicts. Do not turn service failures into an authoring gate.

## Offer

Present placement, the decision, affected prior wording, and unresolved conflicts
together. Verify the changed records once through the owning tools. Record existing
authorization and proceed; ask only for authority not supplied. Accept a reversal's
successor before `vaultspec-core vault adr supersede OLD --by NEW`.
