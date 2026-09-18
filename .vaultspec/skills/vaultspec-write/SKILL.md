---
name: vaultspec-write
description: Write a proportionate implementation plan when scope or progress needs durable sequencing, after assessing decision coverage.
---

# Plan (vaultspec-write)

Produces the sequence execution can resume across sessions. Apply the vaultspec system
section's routing and approval contract. A plan may reuse governing ADRs or have none
when no costly decision is involved. Drafting does not authorize execution.

## Steps

- Discover governing decisions across features and read the relevant ADRs and evidence.
  Reuse accepted decisions unchanged. Route uncovered costly choices to `vaultspec-adr`;
  a draft may link proposed decisions, but dependent execution waits for acceptance.
- Discover the affected code and exact paths. Expected new files are identified as
  creation work. Record the coverage assessment and authorized scope in the Description,
  particularly when no ADR governs.
- Scaffold:
  `vaultspec-core vault add plan --feature {feature} --tier <L1..L4> [--related <adr-stem> ...]`
  (or `create`). Link each governing ADR; inherit its evidence transitively. Optional
  direct evidence links do not replace governing ADRs.
- Read `.vaultspec/templates/plan.md` for tiers, identifiers, row syntax, and cohesive
  granularity. Build structure with `plan_edit` or the `vaultspec-core vault plan`
  verbs. Author Description, Parallelization, and Verification through body editing.
- Draft locally or dispatch `vaultspec-writer` with the scaffolded plan, assessed
  coverage, scoped work, and governing documents, if any.
- Verify with `vaultspec-core vault check all` and `vaultspec-core vault plan check`.
- Present the plan. Persist existing scoped authorization with `Approved yyyy-mm-dd` as
  the first Description line and its basis. Ask only when authorization is missing.
  Gather missing evidence with the appropriate evidence skill, not an automatic new ADR.

## Rules

- Select the smallest useful tier; promote only when containers clarify dependencies.
- A Step is one cohesive, verifiable commit. Related changes across several files may
  share a Step with bounded scope; unrelated outcomes need separate Steps.
- Every governing ADR goes once in `related:`. When several govern different parts, map
  them in the Description to Steps at L1 or the relevant containers at higher tiers.
- Wiki-links belong only in `related:`.
