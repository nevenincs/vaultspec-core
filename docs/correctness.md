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
answers it completely: a dangling link either resolves or it does not.

*Is this change right?* is not mechanical, and nothing in the toolchain can answer it.
What the framework does instead is refuse to let the question go unasked, and keep the
answer where the next person will find it.

Confusing the two is the common failure. A green check suite says the documents are well
formed. It says nothing about whether the code does what the decision record said it
should.

## What is actually enforced

Three things are mechanical, and they are the whole list.

`vaultspec-core install` writes a `.pre-commit-config.yaml` carrying four hooks, the
first of which runs `vault check all`, so a malformed document blocks the commit. Its
scope is the whole vault rather than the files you staged: the hooks pass no filenames,
and the Markdown type filter decides only whether they fire, not what they read. One of
the four mutates - `vault sanitize annotations` strips generated template annotations,
across the vault by the same rule - which is why the
[framework manual](framework.md) treats enabling this in a shared checkout as a
decision rather than a default.

The `schema` check requires the chain to hold: an ADR must reference the research behind
it, and a plan must reference its ADR. A plan that appeared from nowhere fails.

The `modified-stamp` check compares each document's body against the fingerprint stored
in its frontmatter, so an audit edited quietly after the fact is detectable. Rewriting
history leaves a trace.

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

Installing vaultspec seeds a system prompt into each provider it manages, meaning each
coding-agent integration such as Claude, Codex, or Gemini. Two of its mandates are about
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

A guard you have only seen pass has not been shown to guard anything.

A passing test cannot distinguish two cases: the code is correct, or the test never
looked. A gate that reads the wrong file, a comparison against itself, an assertion
after an early return: all pass exactly as convincingly as the real thing.

So prove the guard can fail, in one uninterrupted sequence.

1. Break the thing the guard exists to catch. For a test asserting that a config loader
   rejects a negative timeout, that means making the loader accept one, not deleting the
   test.
1. Run that guard alone, not the suite: `pytest path/to/test_file.py::test_name` or your
   project's equivalent. Running everything does not show that this guard fired.
1. Watch it fail on the assertion that names the problem. If it fails on a different
   assertion, or errors instead of failing, the guard is testing something adjacent to
   what you think. Fix the guard, not the mutation.
1. Restore with `git checkout -- <file>` or `git stash pop`, so the restore is
   verifiable rather than remembered.
1. Run it again and watch it pass.

Do not leave the mutation on disk across a pause or a handoff. Nothing detects a
forgotten mutation, and the next agent to read the tree will treat it as intended code.

Record the failing command and its message alongside the passing one, in the ledger row
for the step that added the guard, or in `## Notes` if it needs more than a line.

This takes about a minute per guard. Skip it and the suite's green is uninformative.

## What the execution record contains

Closing a Step writes an execution record. The shipped pipeline produces one record per
Step, scaffolded against the Step it documents:

```bash
vaultspec-core vault add exec --feature payment-retries --step S01   --related 2026-02-06-payment-retries-plan
```

The filename carries the Step's position, so `S01` under phase `P01` becomes
`.vault/exec/2026-02-06-payment-retries/2026-02-06-payment-retries-P01-S01.md`, and the
`step_id` frontmatter field carries the canonical `S01`. That binding is what lets
`vault check exec-mapping` pair every record with a live Step.

Its `## Changes` section is a mechanical log, one line per path touched:

```
- `M` `src/billing/retry.py`
- `A` `src/billing/tests/test_retry.py`
- `D` `src/legacy/shim.py`
```

The operations are `A` added, `M` modified, `D` deleted, and `R old -> new` renamed. No
prose: the Step row already states the intent and the commit carries the diff.

One optional final line names a check that was run:

```
- `verify:` `pytest src/billing/tests/test_retry.py` -> `pass`
```

That line is the difference between "this was done" and "this was checked". It is
optional, which makes its absence information too: a Step with no `verify:` line is a
Step nobody claims to have checked.

A `## Notes` section exists for exceptions only: work skipped, a scaffold left behind, a
persistent failure, a decision that went against the Step as written. An absent Notes
section is the correct state. An empty one is noise, and no check reports it, so leaving
one behind is on you.

### The consolidated ledger

A plan's records can also be folded into a single append-only ledger, one per plan,
whose rows carry the Step id in the first column:

```
- `S01` `M` `src/billing/retry.py`
- `S02` `D` `src/legacy/shim.py`
```

`vaultspec-core vault exec log` appends rows directly, creating the ledger on first use.
`vaultspec-core vault exec fold` converts a feature's existing per-Step records into
one; it deletes those records, so it refuses to run without `--force` and offers
`--dry-run` to preview.

Both shapes are first-class: `exec-mapping` reads a per-Step record through its
`step_id` and a ledger through the ids in its rows. The folded form exists because a
large vault accumulated more prose in per-Step records than any consumer read.

## What to run before you call something done

```bash
vaultspec-core vault check all --fix
```

`--fix` rewrites documents, so read the diff before committing it. Then the project's
own tests and gates, then `/vaultspec-code-review`, in that order. The check suite is
fastest and catches mechanical damage; the tests catch behaviour; the review compares
the change against the intent, and is the only one of the three that can notice you
solved the wrong problem.
