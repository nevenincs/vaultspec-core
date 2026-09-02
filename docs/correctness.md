# The correctness workflow

Vaultspec does not make code correct. It makes the claim that code is correct into
something with a record behind it: a decision that says what was intended, a plan that
says what was done, and an audit that says who checked and what they found. This page
covers how that runs in practice, and where the framework stops asking and starts
enforcing.

For the stages themselves, see the [framework manual](./framework.md). For the commands
that check a vault mechanically, see
[verifying a workspace and a vault](./verification.md).

## Two different questions

*Does this vault hold together?* is mechanical, and the check suite answers it
completely: a dangling link either resolves or it does not.

*Is this change right?* is not mechanical, and nothing in the toolchain can answer it.
What the framework does instead is refuse to let the question go unasked, and keep the
answer where the next person will find it.

Confusing the two is the common failure. A green check suite says the documents are well
formed. It says nothing about whether the code does what the decision record said it
should.

## The review gate

Review is the fifth stage, and it is not optional. Run it at the end of every execute
cycle, before a feature is called done and before a pull request goes up:

```
/vaultspec-code-review
```

It reads the plan, the decision record, and the research behind the change, identifies
what was actually modified, and writes an audit:

```
vaultspec-core vault add audit --feature payment-retries
```

The audit carries three sections and they do different work. **Scope** records what was
examined, which is what makes an absence meaningful later - a defect outside the
recorded scope was not missed, it was not looked at. **Findings** is a log, one
subsection per finding. **Recommendations** ties each finding to an action.

An audit with no findings is a real outcome and worth writing. What makes it worth
anything is the scope line above it.

## What the framework enforces on the agent

Installing vaultspec seeds a system prompt into each provider it manages. Two of its
mandates are about correctness specifically, and they exist because the failure they
describe is common enough to need naming.

On tests:

> Never accept tautological tests, and avoid mocks, skips, patches, stubs, and fakes.
> These often mask code quality in favor of passing tests. Your responsibility is to
> craft high-quality code, not to make tests pass.

On analysis:

> Never add skips to linting and type checking; instead tackle the core issue that
> caused the type and lint errors.

Both are aimed at the same move: making the signal green without making the code right.
An agent under time pressure reaches for a skip the way anyone does, and the instruction
to stop is worth more than the instruction to try harder.

## A guard you have only seen pass has not been shown to guard anything

This is the part most worth internalising, because it is the one that looks like
pedantry until it costs you something.

A test that passes tells you two things are indistinguishable: that the code is correct,
and that the test is not looking. A gate that reads the wrong file, a comparison against
itself, an assertion after an early return - all of them pass exactly as convincingly as
the real thing.

So prove the guard can fail, in one uninterrupted sequence:

1. Break the thing the guard exists to catch.
1. Run the guard alone. Watch it fail, on the assertion that names the problem.
1. Restore.
1. Run it again. Watch it pass.

Do not leave the mutation on disk across a pause or a handoff. Record both directions
where the guard's next reader will find them - usually the execution record for the step
that added it.

The cost is a minute. The alternative is a suite that has never once told you anything
you did not already believe.

## Where the record goes

Each closed step writes an execution record: one line per path touched, and a `verify:`
line naming the command that was run and whether it passed. That line is the difference
between "this was done" and "this was checked".

A record's `## Notes` section exists for exceptions only - work skipped, a scaffold left
behind, a persistent failure, a decision that went against the step as written. An
absent Notes section is the correct state. An empty one is a finding.

## What to run before you call something done

```
vaultspec-core vault check all --fix
```

Then the project's own tests and gates, then `/vaultspec-code-review`, in that order.
The check suite is fastest and catches the mechanical damage; the tests catch behaviour;
the review catches intent, which is the only one of the three that can notice the change
solved the wrong problem.
