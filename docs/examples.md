# A feature end to end

One feature carried from an open question to a vault that tells you what is still
unwritten. Every command below was run in a fresh project, and every response is the
tool's own output, trimmed where noted.

Two things to know before following along. Run everything from the project root. And
document names carry the date they were scaffolded, so the `2026-08-28` stems below will
be today's date in your project: substitute the stems the commands print back at you
rather than copying these.

The commands are the same ones an AI assistant runs through the pipeline skills. Typing
them yourself is the way to see what the assistant is doing.

For what the stages mean, read the [framework manual](./framework.md). For the document
rules the commands enforce, read [document syntax](./syntax.md).

## Install

```
vaultspec-core install
```

```
Installed vaultspec
  Target <project>
  Synced 3 rules, 10 skills, 10 agents
  Enabled claude, gemini, antigravity, codex
  Installed MCP server
```

The counts change between releases. This run was on 0.1.73.

## Orient

Nothing is in flight yet:

```
vaultspec-core status
```

```
Vault Status

Plans in flight  (at least one open step)
  none

Recent changes
  none
```

Trimmed: the real report also lists active features and discovery state.

## Research

```
vaultspec-core vault add research --feature payment-retries
```

```
WARNING  Potential unhydrated placeholder found in template: {topic}
Created: <project>/.vault/research/2026-08-28-payment-retries-research.md
```

The warning is expected. The template ships with a `{topic}` placeholder and the command
reports that it is still there. Fill it in along with the body prose.

Each command also prints a `Next action` block naming the command that follows, which is
how you can walk the pipeline without memorising it. Those blocks are trimmed from the
output below.

## Scaffold the decision record

Pass the research document with `--related` so the decision record links back to what
grounds it:

```
vaultspec-core vault add adr --feature payment-retries \
  --related 2026-08-28-payment-retries-research
```

```
WARNING  Potential unhydrated placeholder found in template: {title}
Created: <project>/.vault/adr/2026-08-28-payment-retries-adr.md
```

This creates the record. The decision itself is still yours to write, and the last
section of this page shows the check that refuses to let you forget.

## Plan

The tier decides how much structure the plan carries: `L1` is steps only, `L2` groups
them under phases, `L3` adds waves above phases, `L4` adds an epic frame. This feature
is one coherent phase of work, so `L2`:

```
vaultspec-core vault add plan --feature payment-retries --tier L2 \
  --related 2026-08-28-payment-retries-adr
```

```
Created: <project>/.vault/plan/2026-08-28-payment-retries-plan.md
```

Add a phase, then a step under it for each action:

```
vaultspec-core vault plan phase add .vault/plan/2026-08-28-payment-retries-plan.md \
  --title "Retry ceiling" \
  --intent "Read the ceiling from configuration instead of the constant."
```

```
Added Phase `P01`. (Preserved 3 unknown blocks)
```

```
vaultspec-core vault plan step add .vault/plan/2026-08-28-payment-retries-plan.md \
  --phase P01 \
  --action "Read the retry ceiling from configuration" \
  --scope "src/billing/retry.py"
```

```
Added Step `P01.S01`. (Preserved 3 unknown blocks)
```

```
vaultspec-core vault plan step add .vault/plan/2026-08-28-payment-retries-plan.md \
  --phase P01 \
  --action "Cover the ceiling with a test that fails when it is ignored" \
  --scope "tests/test_retry.py"
```

```
Added Step `P01.S02`. (Preserved 3 unknown blocks)
```

"Preserved 3 unknown blocks" counts the prose blocks the command rewrote around without
touching. It is reporting that your writing survived the edit.

Scope paths name the files the step will touch. They do not have to exist yet.

Those two commands wrote these rows into the plan:

```markdown
### Phase `P01` - Retry ceiling
- [ ] `P01.S01` - Read the retry ceiling from configuration; `src/billing/retry.py`.
- [ ] `P01.S02` - Cover the ceiling with a test that fails when it is ignored; `tests/test_retry.py`.
```

Two actions, two rows. One row covering both could only be open or closed, so a
half-finished step would have nowhere to be recorded.

## Orient again

```
vaultspec-core status
```

```
Plans in flight  (at least one open step)
  2026-08-28-payment-retries-plan   L2   -   P0/1   0/2 steps   0%   next P01.S01      2026-08-28
```

The next open step is named. Start there.

## Execute

Write the code the step describes, whether by hand or by asking your assistant to work
the plan. Then record what changed and close the row:

```
vaultspec-core vault add exec --feature payment-retries --step S01
```

```
Created: <project>/.vault/exec/2026-08-28-payment-retries/2026-08-28-payment-retries-P01-S01.md
```

```
vaultspec-core vault plan step check .vault/plan/2026-08-28-payment-retries-plan.md S01
```

```
Closed Step `S01`. (Preserved 3 unknown blocks)
```

Fill the record's `## Changes` section with one line per path you touched. Pass the bare
step id, `S01`, to both commands: `P01.S01` is the display path that status prints, and
the command derives the phase segment of the filename from the plan.

Without `--step`, the record is not bound to a step. Its frontmatter keeps the
`step_id: '{step_id}'` placeholder, `related` stays empty, and the file lands as
`2026-08-28-payment-retries-exec.md` rather than inside the feature folder.

Status moves:

```
  2026-08-28-payment-retries-plan   L2   -   P0/1   1/2 steps   50%   next P01.S02      2026-08-28
```

Repeat both commands for `S02`, and the plan reaches `2/2 steps 100%`.

## Close the trail

With every step closed, scaffold the audit:

```
vaultspec-core vault add audit --feature payment-retries
```

```
WARNING  Potential unhydrated placeholder found in template: {title}
Created: <project>/.vault/audit/2026-08-28-payment-retries-audit.md
```

The trail so far:

```
vaultspec-core vault list
```

```
Vault documents
  2026-08-28-payment-retries-adr adr #payment-retries 2026-08-28
  2026-08-28-payment-retries-audit audit #payment-retries 2026-08-28
  2026-08-28-payment-retries-plan plan #payment-retries 2026-08-28
  2026-08-28-payment-retries-research research #payment-retries 2026-08-28
  2026-08-28-payment-retries-P01-S01 exec #payment-retries 2026-08-28
  2026-08-28-payment-retries-P01-S02 exec #payment-retries 2026-08-28
  6 documents
```

Six documents, one feature tag.

## The vault fails its own checks, on purpose

Run the checks on this vault as it stands and it fails:

```
vaultspec-core vault check all
```

```
  Total: 4 errors, 27 warnings
```

That is correct. Scaffolded documents are not finished documents: every one still
carries template annotations and unreplaced placeholders, because nobody has written the
prose yet.

Both blocks above and below are the report's last line. The full run prints a
status row for every check first - on one vault that is eighty-eight lines and
forty-one rows, since a check with several findings prints several - and the
counts are what the rest of this section reasons about.

`--fix` clears what is mechanical:

```
vaultspec-core vault check all --fix
```

```
  Total: 4 errors, 19 warnings, 19 fixed
```

Nineteen repairs, and the four errors stay. The two nineteens do not subtract from the twenty-seven above: `fixed` counts the repairs applied, and the warning count beside it is a fresh reading taken afterwards, against a corpus those repairs have changed. Repairing one thing can settle a check that was not counted and unsettle one that was, so compare runs rather than doing the arithmetic.

The four errors are the placeholders:

```
vaultspec-core vault check placeholders
```

```
  x placeholders: 4 errors
    x .vault/adr/2026-08-28-payment-retries-adr.md
      Unreplaced template placeholder {title} - replace it with the intended value before committing
    x .vault/adr/2026-08-28-payment-retries-adr.md
      Unresolved template enum {proposed|accepted|rejected|superseded|deprecated} - choose one option (proposed, accepted, rejected, superseded, deprecated) and replace it
    x .vault/audit/2026-08-28-payment-retries-audit.md
      Unreplaced template placeholder {title} - replace it with the intended value before committing
    x .vault/research/2026-08-28-payment-retries-research.md
      Unreplaced template placeholder {topic} - replace it with the intended value before committing
```

No command can fill those, because each one is a decision. No tool can choose between
`proposed` and `accepted`: only you know which the decision is.

Writing the ADR's title and choosing its status clears both of its errors:

```
vaultspec-core vault check placeholders
```

```
  x placeholders: 2 errors
    x .vault/audit/2026-08-28-payment-retries-audit.md
      Unreplaced template placeholder {title} - replace it with the intended value before committing
    x .vault/research/2026-08-28-payment-retries-research.md
      Unreplaced template placeholder {topic} - replace it with the intended value before committing
```

The total moves with it, from four errors to two. Finish the research topic and the
audit title the same way and the vault comes back clean.

The checks are a worklist of what is left to write. They pass once the prose is written,
not when the files are created.

## Where to go next

This run stops where the vault is written, which is one step short of where a real one
stops. Nothing above says what to stage, and nothing installs a gate:

- [Verifying a workspace and a vault](./verification.md) covers every check this page ran
  and what each one proves.
- [The framework manual](./framework.md) opens with what to commit and what the managed
  `.gitignore` block keeps out, including the one file it deliberately does not exclude.
- [Correctness](./correctness.md) is where the gate lives: the install writes
  `.pre-commit-config.yaml` and no git hook, so nothing checks a commit until you install
  the `pre-commit` tool and run `pre-commit install`.
