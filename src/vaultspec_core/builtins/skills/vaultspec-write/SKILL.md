---
name: vaultspec-write
description: Write the implementation plan for multi-session work. Use once the ADR (or ADR cluster) it executes is approved and the work outlives this session.
---

# Plan (vaultspec-write)

Produces a plan: the approved sequence of Steps that execution resumes from across
sessions. Precondition: every ADR the plan executes is `accepted`. If invoked
standalone, locate those ADRs first. If one is still `proposed`, present it again and
stop; if none exists, stop and name `vaultspec-adr` as the next run. This skill
terminates within one run; the plan it writes does not.

## Steps

- Read the authorizing ADRs and their research or reference records in full.

- Ground per the `vaultspec-discovery` rule, code first: map the files and symbols the
  plan will touch, so Steps name real paths.

- Scaffold:
  `vaultspec-core vault add plan --feature {feature} --tier <L1..L4> --related <adr-stem> [--related ...]`
  (or the `create` tool), one `--related` per authorizing ADR. Read
  `.vaultspec/templates/plan.md`; its hint blocks are the canonical source for tiers,
  identifiers, the Step row contract, and the no-compression rule.

- Build the structure only through the plan verbs (`plan_edit` tool, or
  `vaultspec-core vault plan step | phase | wave | epic intent | tier`); author the
  Description, Parallelization, and Verification sections as body prose. Draft in this
  run, or dispatch the `vaultspec-writer` persona with "Create an implementation plan
  for `{feature}` from the ADR(s) `[[...-adr]]`, conforming to the plan template's hint
  blocks; the tier is already set."

- Verify with `vaultspec-core vault check all` and `vaultspec-core vault plan check`.

- Present the plan and stop:

  ```markdown
  The Plan is ready: [[yyyy-mm-dd-{feature}-plan]]
  Do you want to approve the Plan, or request changes?
  ```

  **Execution starts only after an approval reply.** On approval, write
  `Approved yyyy-mm-dd` as the first line of the Description. On requested changes,
  revise through the plan verbs and present again; on a knowledge gap, stop and name
  `vaultspec-research` as the next run.

## Rules

- **Tier.** Select by the HIERARCHY AND TIERS hint block; between two tiers take the
  smaller and `tier promote` later.
- **Granularity.** Every Step is one checkbox row naming one file or one cohesive area,
  one commit's worth of work. No per-row references; authorizing documents go once in
  `related:`. N self-similar actions are N rows.
- **Cardinality.** Per the vaultspec section; when several ADRs feed the plan, the
  Description states which Wave or Phase each governs.
- **Links.** Wiki-links only in `related:`; the body carries none.
