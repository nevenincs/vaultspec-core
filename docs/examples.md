# A feature end to end

This is one feature carried from an open question to a closed audit. Every command and
every response is from a real run in an empty project, with the project directory
shortened to `<project>` in paths.

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

## Orient

Nothing's in flight yet, and the command says so plainly:

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

## Research

```
vaultspec-core vault add research -f payment-retries
```

```
WARNING  Potential unhydrated placeholder found in template: {topic}
Created: <project>/.vault/research/2026-08-28-payment-retries-research.md
```

The warning isn't a failure. The template arrives with a `{topic}` placeholder and the
command tells you it's still there. Fill it in along with the body prose.

## Decide

Pass the research document with `-r` so the decision record links back to what grounds
it:

```
vaultspec-core vault add adr -f payment-retries -r 2026-08-28-payment-retries-research
```

```
WARNING  Potential unhydrated placeholder found in template: {title}
Created: <project>/.vault/adr/2026-08-28-payment-retries-adr.md
```

## Plan

The tier decides which containers the plan has. This feature has one coherent phase of
work, so `L2`:

```
vaultspec-core vault add plan -f payment-retries --tier L2 -r 2026-08-28-payment-retries-adr
```

```
Created: <project>/.vault/plan/2026-08-28-payment-retries-plan.md
```

Add a phase, then the steps under it:

```
vaultspec-core vault plan phase add .vault/plan/2026-08-28-payment-retries-plan.md \
  --title "Retry ceiling" \
  --intent "Read the ceiling from configuration instead of the constant."

vaultspec-core vault plan step add .vault/plan/2026-08-28-payment-retries-plan.md \
  --phase P01 \
  --action "Read the retry ceiling from configuration" \
  --scope "src/billing/retry.py"
```

```
Added Phase `P01`. (Preserved 3 unknown blocks)
Added Step `P01.S01`. (Preserved 3 unknown blocks)
```

"Preserved 3 unknown blocks" means the command rewrote the rows and left your prose
alone.

The rows it wrote:

```
### Phase `P01` - Retry ceiling
- [ ] `P01.S01` - Read the retry ceiling from configuration; `src/billing/retry.py`.
- [ ] `P01.S02` - Cover the ceiling with a test that fails when it is ignored; `tests/test_retry.py`.
```

Two rows for two actions. A single row saying "read the ceiling from configuration and
test it" couldn't be half closed, and its execution record couldn't say which half
happened.

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

Do the work, then record it and close the row:

```
vaultspec-core vault add exec -f payment-retries --step S01
vaultspec-core vault plan step check .vault/plan/2026-08-28-payment-retries-plan.md S01
```

```
Created: <project>/.vault/exec/2026-08-28-payment-retries/2026-08-28-payment-retries-P01-S01.md
Closed Step `S01`. (Preserved 3 unknown blocks)
```

`--step S01` matters. Without it you get an unbound record with the placeholder still in
its frontmatter, filed under the wrong name.

Status moves:

```
  2026-08-28-payment-retries-plan   L2   -   P0/1   1/2 steps   50%   next P01.S02      2026-08-28
```

## Verify

After the last step closes, write the audit:

```
vaultspec-core vault add audit -f payment-retries
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

One feature tag, six documents, the whole decision trail.

## What the check says about scaffolds

Run the checks on this vault as it stands and it fails:

```
vaultspec-core vault check all
```

```
  Total: 4 errors, 27 warnings
```

That's correct, and worth understanding. Scaffolded documents aren't valid documents.
Every one of them still carries template annotations and unfilled placeholders, because
nobody has written the prose yet.

`--fix` clears what's mechanical:

```
vaultspec-core vault check all --fix
```

```
  Total: 4 errors, 19 warnings, 19 fixed
```

Nineteen repairs, and the errors stay. Those are the placeholders:

```
  x placeholders: 4 errors
    x .vault/adr/2026-08-28-payment-retries-adr.md
      Unreplaced template placeholder {title} - replace it with the intended value before committing
    x .vault/adr/2026-08-28-payment-retries-adr.md
      Unresolved template enum {proposed|accepted|rejected|superseded|deprecated} - choose one option
    x .vault/audit/2026-08-28-payment-retries-audit.md
      Unreplaced template placeholder {title} - replace it with the intended value before committing
```

No command can fill those, because each one is a decision. The status enum on the
decision record is the clearest case: only you know whether the decision was accepted or
is still proposed.

Fill one and it leaves the list. Write the research topic, re-run the check, and that
document stops being reported.

The check tells you what's left to write. A green vault means the documents are
finished, not merely created.

## Where to go next

[Verifying a workspace and a vault](./verification.md) covers every check this page ran
and what each one proves.
