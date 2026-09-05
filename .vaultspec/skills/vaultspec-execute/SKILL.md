---
name: vaultspec-execute
description: Execute an approved plan Step by Step, across sessions. Use to start or resume a plan; it is the only skill that spans sessions.
---

# Execute (vaultspec-execute)

Works an approved plan from its next open Step, leaving a checkpoint after every Step so
any later session resumes without re-reading the cluster. Precondition: the plan has an
approval reply from the user. A plan without one is not executed.

## Resume

- `vaultspec-core status <feature>` (or the `status` tool) names the next open Step. A
  plan whose Description lacks an `Approved` line is presented again first.
- On the plan's first entry read it whole; on resume, read the next Step's row and the
  ADR sections it depends on.
- Ground the Step per the `vaultspec-discovery` rule before editing.
- A dispatched worker skips orientation (the orchestrator did it) and works its assigned
  container from the named Step onward.

## Per Step

- Implement exactly the Step's action in the files it names. Run the project's tests,
  lint, and type checks.
- **Blocker:** if the Step admits implementations of different scope, names a path that
  does not exist, or depends on something missing, stop and ask the user (a worker
  raises it to the orchestrator and waits). The answer goes into the row via `plan_edit`
  and is quoted back in the reply; then continue. Never resolve a blocker on your own
  judgment. Otherwise do not ask between Steps.
- Log the Step:
  `vaultspec-core vault exec log --feature {feature} --step S## --related <plan-stem> --row M:path`
  (or the `log` tool), one `--row` per path touched, `--verify '<cmd>=pass'` when a
  check ran, `--note` only on exception. The plan row states the intent and the commit
  carries the diff.
- Close the Step: `plan_progress` tool or `vaultspec-core vault plan step check`. Never
  edit the checkbox by hand.
- Commit once per Step, code, ledger, and plan together, adding the `Vaultspec-Step`
  trailer (`vaultspec-core vault plan trailer emit --step S##`) when the repository
  already uses it. Code never cites the vault.

## Delegation

Do the Steps yourself unless the plan's Parallelization section names containers that
may run concurrently; then dispatch executor personas (`vaultspec-low-executor`,
`vaultspec-standard-executor`, or `vaultspec-high-executor` by the Step's difficulty) at
approved Steps, each told the plan stem, the feature tag, its container, and its
starting Step id, and to follow this skill as a worker; they return in their persona's
Return message format. Workers never change plan structure; that routes back to you.

## Phase close and finish

- At each point of the review cadence in the vaultspec section, run
  `vaultspec-code-review`; a worker under `vaultspec-team` reports the close to its
  supervisor instead, who reviews. `critical` or `high` findings reopen the affected
  Steps (`vaultspec-core vault plan step uncheck`) and are fixed before continuing;
  lower findings are recorded and fixed only under a Step the user approves.
- At `L4`, report Wave and Epic completion against the external artifact named in the
  plan's `## Epic intent`.
- When every Step is closed and the last review passes, report the plan complete with
  the modified files and the audit's status.
