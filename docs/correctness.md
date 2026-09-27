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
implementation scope, existing check results, active check owners, and the feature's
documents. It compares the integrated result with the plan and any governing ADRs,
consulting supporting evidence as needed. Record scope, findings, and recommendations in
the feature's rolling audit. A change without a plan is reviewed in the reply and does
not require an audit record.

For planned work, review at each Phase close, at plan close, and before handoff for
merge or completion. Combine coincident reviews. An L1 plan has no Phases, so it has no
Phase-close gate. Each Step needs verification evidence for its changed behavior;
applicable results can be reused across execution and review.

Trace the affected workflow across its components: do the interfaces agree, do failure
paths behave as intended, and do the tests cover the promised result? For documentation
or framework changes, read the pages and instructions together for conflicting advice.
Separate file reviews alone do not establish that the whole workflow works.

To scaffold the feature's first audit manually, run:

```sh
vaultspec-core vault add audit --feature payment-retries
```

Replace `payment-retries` with your feature's tag. This creates a template, not a
completed review. Record the reviewed scope and result even when no problems are found;
append later reviews and resolutions to the same audit.

## Select supporting context

When discovery yields several possible callers, tests or decision passages, use
`vaultspec-core review context` to select a bounded set of supporting evidence. Pass a
review objective, the diff base, and repeated `--candidate path:start-end` locators. Add
`--head REF` for a committed target; otherwise the command reads tracked working-tree
changes, including staged changes. Untracked files are excluded.

The configured `VAULTSPEC_CORE_TYPESAFE_API_KEY` opts into sending the objective,
bounded diff and candidate passages to TypeSafe. Missing credentials, rejected keys,
timeouts and service failures preserve discovery order. `--no-hosted` disables the
request. The result reports selected passages, unselected locators, exclusions, hosted
status and usage. `--previous FILE` reuses an identical selection judgment for up to one
hour, provided a key remains enrolled; reuse does not assert current connectivity.

Share one selection among reviewers. Keep the full diff and governing decisions in the
review and expand context when necessary. Selection is optional and cannot establish a
verdict, verification result or complete coverage. See the
[command reference](CLI.md#vaultspec-core-review-context) for bounds and input rules.

## Share verification evidence

Review starts with a defined diff base and target, including any uncommitted changes.
Reuse CI results, execution logs, or worker handoffs that identify the check command and
scope, checked state, outcome, relevant environment, and result location. Check whether
the relevant code, tests, dependencies, or check conditions have changed. Matching a
commit identifier alone is insufficient when the working tree has changed; an unrelated
commit does not automatically invalidate evidence.

The supervisor assigns one owner to shared, expensive, or stateful checks; a solo agent
owns its checks. Reviewers inspect applicable results and continue code analysis while
checks run. Independent focused checks can run concurrently when resources allow.
Separate worktrees do not isolate CPU, memory, ports, services, or external quotas.
These are coordination instructions for agents, not an automatic test scheduler.

Run additional checks for a specific coverage gap, changed inputs, a suspected defect,
or a project requirement. Choose the smallest useful check. Independent review requires
independent judgment, not a second execution of every command. Required long-running
checks remain required: report their owner and next action if they are unfinished or
cannot run. Timeouts and infrastructure failures do not establish a code defect.

Report findings and verification coverage separately. Critical findings yield `FAIL`;
high findings yield `REVISION REQUIRED`. Otherwise, unresolved required verification
yields `PENDING`; applicable passing evidence yields `PASS`. A pending review neither
invents a defect nor reopens a Step by itself. Resume it with the missing results and
any changed interactions, keeping completed analysis.

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

When a guard's ability to detect its target defect is in doubt, or the project requires
it, a focused mutation check can establish that behavior. This is not a requirement to
revalidate every test. Coordinate with the check owner before mutating even an isolated
copy, since its checks may still use shared resources:

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
1. Ensure applicable evidence covers the project's required tests, linting, formatting,
   and type checks. Coordinate missing checks with their owner.
1. Review the implementation against the approved scope and any governing decisions
   using the [review step](#review-the-change). Address findings and rerun affected
   checks.

Review the final diff before committing.
