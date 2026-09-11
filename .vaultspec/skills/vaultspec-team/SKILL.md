---
name: vaultspec-team
description: Supervise several workers over one approved plan. Use when the plan's Parallelization section names containers that may run concurrently.
---

# Team (vaultspec-team)

A coordination policy for executing an approved plan with parallel workers; the host
environment dispatches, sequences, and monitors them. It adds nothing to the pipeline:
each worker runs `vaultspec-execute` on its assigned container, and the supervisor keeps
the plan and the review gate. For single-persona work, load the persona directly.

## Shape

- Assign the Steps or whole containers the plan declares: Steps at L1, Steps or Phases
  at L2, and suitable containers at higher tiers. The plan's Parallelization section
  says which may run concurrently.
- Each worker follows `vaultspec-execute` as a dispatched worker: one commit and its
  ledger rows per Step, Steps closed through the plan verbs, blockers raised to the
  supervisor, assignment completion reported to the supervisor. Report Phase close only
  when a Phase exists.
- Workers never change plan structure; the supervisor applies changes through the plan
  verbs under the system's scoped approval contract. Routine corrections need no new
  approval. Isolate working trees or serialize shared plan, ledger, and commit writes;
  workers have disjoint source ownership and never commit another worker's changes.
- The supervisor holds the review gate, `vaultspec-code-review` at each point of the
  review cadence in the vaultspec section. A Phase is reported done to the user only
  after its review.
- Workers report through `SendMessage`, including "nothing found".
