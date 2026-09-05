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

- Assign whole containers (a Phase, or a Wave) to workers, never fragments; the plan's
  Parallelization section says which may run concurrently.
- Each worker follows `vaultspec-execute` as a dispatched worker: one commit and its
  ledger rows per Step, Steps closed through the plan verbs, blockers raised to the
  supervisor, Phase close reported to the supervisor.
- Workers never change plan structure; the supervisor applies changes through the plan
  verbs and presents again any Step whose action changed.
- The supervisor holds the review gate, `vaultspec-code-review` at each point of the
  review cadence in the vaultspec section. A Phase is reported done to the user only
  after its review.
- Workers report through `SendMessage`, including "nothing found".
