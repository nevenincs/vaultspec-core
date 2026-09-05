# The correctness workflow

vaultspec does not make code correct. It puts a record behind the claim that code is
correct: an Architecture Decision Record (ADR) saying what was intended, an execution
record saying what was done, and an audit saying who checked and what they found.

This page covers how that runs in practice, and is careful to separate what the tooling
checks from what it only asks for.

For the stages themselves, see the [framework manual](./framework.md). For the commands
that check a vault mechanically, see
[verifying a workspace and a vault](./verification.md).

## Two different questions

*Does this vault hold together?* is mechanical, and `vaultspec-core vault check all`
answers it: a dangling link either resolves or it does not. It runs nineteen of the
twenty checks. The twentieth, `code-boundary`, reads your source for references back
into the vault and is run on its own, so a clean run here says nothing about that
boundary.

*Is this change right?* is not mechanical, and nothing in the toolchain can answer it.
What the framework does instead is refuse to let the question go unasked, and keep the
answer where the next person will find it.

Confusing the two is the common failure. A green check suite says the documents are well
formed. It says nothing about whether the code does what the decision record said it
should.

## What is actually enforced

Three things are mechanical, and they are the whole list.

`vaultspec-core install` writes a `.pre-commit-config.yaml` carrying four hooks, the
first of which runs `vault check all`. That file is configuration and not a git hook:
until you install the `pre-commit` tool and run `pre-commit install`, nothing runs it
and a commit carrying vault errors is accepted. Once it is wired, a malformed document
blocks the commit. Its scope is the whole vault rather than the files you staged: the
hooks pass no filenames, and the Markdown type filter decides only whether they fire,
not what they read. One of the four mutates - `vault sanitize annotations` strips
generated template annotations, across the vault by the same rule - which is why the
[framework manual](framework.md) treats enabling this in a shared checkout as a decision
rather than a default.

The `schema` check requires the chain to hold: an ADR must reference the research behind
it, and a plan must reference its ADR. A plan that appeared from nowhere fails.

The `modified-stamp` check compares each document's body against the fingerprint stored
in its frontmatter, so an audit edited quietly after the fact is detectable. Rewriting
history leaves a trace.

That third one is detectable rather than blocking, and the distinction matters if you
gate on the exit code. Measured: appending a line to an accepted ADR by hand and
re-running the check reports
`Stale modified stamp ...; the document body no longer matches its attested fingerprint (unstamped edit)`
as a **warning**, and warnings do not raise the exit code. The `schema` failure above is
an error and does. So a pipeline gating on `vault check all` catches the plan that
appeared from nowhere and does not catch the audit rewritten last night; for that one,
read the report rather than the exit status.

Nothing else is enforced. In particular, **no check fails because a feature has no
audit**. The `features` check warns about a plan with no ADR and about a missing feature
index, and says nothing about whether anyone reviewed the work. Review is a discipline
here, not a gate, and the cost of skipping it is paid later rather than at commit time.

## The review step

Run the review at the end of every execute cycle, before a feature is called done and
before a pull request goes up:

```
/vaultspec-code-review
```

That is a slash-command for an AI client. The document it produces is an ordinary vault
document, so you can also scaffold one directly:

```
vaultspec-core vault add audit --feature payment-retries
```

The feature tag must match the one the plan and ADR already carry, which is what binds
the audit to the rest of the trail.

The review reads the plan, the ADR, and the research behind the change, identifies what
was modified, and writes an audit with three required sections. Scope records what was
examined. That is what makes an absence meaningful later: a defect outside the recorded
scope was never looked at, so its absence from Findings proves nothing. Findings is a
log, one subsection per finding. Recommendations ties each finding to an action.

An audit with no findings still belongs in the vault, but only the scope line gives it
meaning, because it says what was searched before the search came up empty.

### What the review does and does not buy you

The reviewer is a separate persona, `vaultspec-code-reviewer`, and it runs read-only:
its tools are limited to reading and searching, so it cannot edit the code it is
judging. That buys real independence from the executor's edits.

It does not buy independence of judgment. The review is dispatched by the same session
that did the work, against the same ADR, so a wrong assumption in the decision record is
one the reviewer inherits rather than catches. What catches that is a person reading the
ADR, which is why the approval checkpoints exist.

Acting on a finding is a normal plan change: reopen the step it belongs to with
`vaultspec-core vault plan step uncheck`, or add a new one with `step add`. Nothing does
this automatically, so a finding recorded and not acted on stays recorded and not acted
on.

## What the framework tells the agent

Installing vaultspec seeds a system prompt into three of the four providers it manages.
Claude and Codex read it as a rule file, `vaultspec-system.builtin.md`, alongside the
others; Gemini reads it as `.gemini/SYSTEM.md`. Antigravity gets rules and skills but no
system prompt, so the mandates below are not in front of it. It also gets a `workflows`
directory, which the installer creates and nothing fills: the harness ships no
workflows, so that folder is there for the provider's own convention rather than for
anything of ours. Measured on a fresh install: the text appears under `.claude/`,
`.codex/`, and `.gemini/`, and nowhere under `.agents/`. Two of its mandates are about
correctness specifically.

On tests:

> Never accept tautological tests, and avoid mocks, skips, patches, stubs, and fakes.
> These often mask code quality in favor of passing tests. Your responsibility is to
> craft high-quality code, not to make tests pass.

On analysis:

> Never add skips to linting and type checking; instead tackle the core issue that
> caused the type and lint errors.

These are instructions, not constraints. Nothing detects a mock or a skip, so both
depend on the agent following them. They exist because an agent under time pressure
reaches for a skip the way anyone does.

Both are aimed at the same move: making the signal green without making the code right.

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
1. Review the implementation against the approved decision and plan using the
   [review step](#the-review-step). Address findings and rerun affected checks.

Review the final diff before committing.
