---
name: vaultspec-execute
description: Implement or resume an approved plan with project conventions, proportionate verification, and durable Step checkpoints.
---

# Execute (vaultspec-execute)

Implement an approved plan within the system's scope and decision constraints. This
skill owns execution practice; the system owns authorization, recovery, and review
cadence, and executor personas own worker coordination and reporting.

## Resume

- Use `vaultspec-core status <feature>` (or `status`) and the system's Execute and
  recover contract. Keep working context to the current assignment, governing
  constraints, relevant verification criteria, and unresolved state.
- A dispatched worker starts at its assigned Step and reuses the orchestrator's
  grounding; inspect affected code as needed.

## Per Step

- Ground the Step per `vaultspec-discovery`. Before adding code, make a bounded search
  for existing implementations, callers, and nearby tests. Reuse suitable code; stop
  discovery when the implementation location and relevant patterns are clear.
- Deliver the Step's intended behavior within its approved scope and file areas. Follow
  local APIs, type hints, dependencies, naming, formatting, and error handling. Apply
  the system's blocker contract to uncovered choices; record routine row corrections
  through `plan_edit`. Workers route plan corrections to the orchestrator.
- Run the project's configured formatting, lint, type checks, and relevant tests. Add or
  update tests when needed to establish changed behavior. Reuse passing evidence while
  affected code, dependencies, and check conditions remain unchanged; share it between
  workers and supervisor. Broaden checks for changed interactions, failures, or explicit
  project requirements.
- Fix in-scope failures and rerun affected checks. If progress remains blocked or needs
  missing authority or input, leave the Step open and report the failure and what is
  needed to continue.

## Checkpoint

- Log the Step:
  `vaultspec-core vault exec log --feature {feature} --step S## --related <plan-stem> --row M:path`
  (or `log`), one `--row` per path touched, `--verify '<cmd>=pass'` or
  `--verify '<cmd>=fail'` for checks actually run, `--note` only on exception.
- Once the Step's required verification passes, close it with `plan_progress` or
  `vaultspec-core vault plan step check`. Never edit the checkbox by hand.
- Commit once per Step, code, ledger, and plan together, adding the `Vaultspec-Step`
  trailer (`vaultspec-core vault plan trailer emit --step S##`) when the repository
  already uses it. Code never cites the vault.

## Delegation

Delegate when it helps and the plan's Parallelization section defines compatible
assignments. Choose `vaultspec-low-executor`, `vaultspec-standard-executor`, or
`vaultspec-high-executor` by difficulty. Supply the plan stem, feature tag, assigned
Steps or container, starting Step id, write ownership, and relevant existing evidence.
Workers follow this skill and their persona's Return message contract. Coordinate shared
metadata and commits; permission to parallelize does not require delegation.

## Review and finish

- Use `vaultspec-code-review` at the system's review cadence, including its rules for
  coincident gates, unchanged work, and corrective findings. Workers report closes to
  their supervisor, who owns review.
- At `L4`, report Wave and Epic completion against the external artifact named in the
  plan's `## Epic intent`.
- When every Step is closed and the last review passes, report the plan complete with
  the modified files and the audit's status.
