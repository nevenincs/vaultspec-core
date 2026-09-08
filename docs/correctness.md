# Review a feature implementation

Review the implementation against its approved scope, any governing architecture
decision records (ADRs), and test evidence. Define which changes the review covers.

<p id="two-different-questions"></p>
<p id="what-is-actually-enforced"></p>

## Check records separately

Run the [workspace and record checks](verification.md) to find metadata and link
problems. Passing these checks doesn't prove the code behaves correctly or that someone
reviewed the feature.

For hook activation and setup choices, see
[project integration settings](framework.md#configure-project-integrations).

<p id="the-review-step"></p>

## Review the change

For planned work, ask your agent to use `vaultspec-code-review`. Give it the
implementation scope and the feature's documents. It compares the integrated result with
the plan and any governing ADRs, consulting supporting evidence as needed. Record scope,
findings, and recommendations in the feature's rolling audit. A routine change without a
plan is reviewed in the reply; it does not need a ceremonial audit.

Formal review occurs at each actual Phase close, plan close, and handoff; combine
coincident reviews. L1 has no Phase-close gate. Review cohesive behavior across changed
components, not separate files or documents as independent gates. Tests and local checks
still run with each Step.

To scaffold the feature's first audit manually, run:

```sh
vaultspec-core vault add audit --feature payment-retries
```

Replace `payment-retries` with your feature's tag. This creates a template; completing
the review requires inspecting the change and writing the audit. Keep an audit even when
the review finds no problems, with its scope recorded.

<p id="what-the-review-does-and-does-not-buy-you"></p>
<p id="what-the-framework-tells-the-agent"></p>

## Act on findings

The review skill directs the agent to report problems without fixing code during the
review. Execution handles fixes within the approved scope through the
[implementation plan](CLI.md#vaultspec-core-vault-plan), then reruns relevant tests and
record checks. Critical or high findings reopen affected Steps and must be fixed before
continuing. New scope or uncovered decisions require authorization. Append review
outcomes and resolutions without erasing earlier findings.

Before accepting the feature, review its assumptions, test evidence, and responses to
the findings. Resolve uncertainty that could change your acceptance decision.

## Proving a guard can fail

Verify that a test detects the defect it targets:

1. Run the focused test and confirm it passes. For pytest, use
   `pytest path/to/test_file.py::test_name`.
1. In an isolated copy of the code being tested, temporarily introduce that defect. For
   a negative-timeout check, make the loader accept a negative timeout without changing
   the test.
1. Run the test against the modified copy. Confirm it fails at the assertion for that
   defect, not from an unrelated error. Investigate any other result before treating the
   test as verified.
1. Undo only your temporary edit. Compare against the pre-test state to confirm that you
   preserved the implementation and any unrelated changes.
1. Rerun the test and confirm it passes again.

Remove the temporary defect before pausing or handing off the work. Record the failing
and passing commands and results with the step's verification evidence.

## What the ledger contains

Log the files changed by a Step, then close the Step separately. Checking a Step does
not record its file changes.

Use the [execution log reference](./CLI.md#vaultspec-core-vault-exec-log) for the
command, supported evidence fields, and ledger format. Keep verification results with
the work they check; a file-change record alone does not show that tests ran.

## What to run before you call something done

1. [Check the feature records and review any repairs](./verification.md#check-records-before-committing).
1. Run the project's tests, linting, and type checks.
1. Review the implementation against the approved scope and any governing decisions
   using the [review step](#review-the-change). Address findings and rerun affected
   checks.

Review the final diff before committing.
