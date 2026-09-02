# Document syntax

Every document in `.vault/` has two halves. The tool owns one and you own the other, and
most trouble comes from editing the half that is not yours.

The tool owns the filename, the frontmatter, and any value derived from the document's
own content. You own the body prose. Editing prose in a scaffolded document is expected.
Hand-writing the rest produces a file that looks correct and fails validation.

For the commands that create and check these documents, see the
[CLI reference](./CLI.md). For the workflow they serve, see the
[framework manual](./framework.md).

## Frontmatter

Every document carries the same five fields:

```yaml
---
tags:
  - '#plan'
  - '#payment-retries'
date: '2026-02-06'
modified: '2026-02-06'
body_schema: 'body-v1'
body_hash: 'sha256:...'
related:
  - '[[2026-02-06-payment-retries-adr]]'
---
```

Three document types add one field each:

| Type  | Extra field | Holds                                                  |
| ----- | ----------- | ------------------------------------------------------ |
| plan  | `tier`      | The complexity tier: `L1`, `L2`, `L3`, or `L4`         |
| exec  | `step_id`   | The canonical identifier of the Step the record covers |
| index | `generated` | Always `true`; the file is rebuilt, never authored     |

Add no fields beyond these. Metadata lives in frontmatter and nowhere else, so an
invented field has no reader and fails the `frontmatter` check.

## The tag pair

Exactly two tags. One names the directory, one names the feature.

| Directory           | Tag          |
| ------------------- | ------------ |
| `.vault/adr/`       | `#adr`       |
| `.vault/audit/`     | `#audit`     |
| `.vault/exec/`      | `#exec`      |
| `.vault/index/`     | `#index`     |
| `.vault/plan/`      | `#plan`      |
| `.vault/reference/` | `#reference` |
| `.vault/research/`  | `#research`  |

The feature tag is kebab-case and identical across every document in the feature's
lifecycle. It is what makes a trail findable: research, decision, plan, execution
records, and audit all carry `#payment-retries`, so one filter returns the whole story.

A third tag reads as a second feature tag and fails validation. Resist the urge to add
`#urgent` or `#frontend`.

## Wiki-links

Links between vault documents are Obsidian-style wiki-links, quoted, and they belong in
`related:` only:

```yaml
related:
  - '[[2026-02-06-payment-retries-research]]'
  - '[[2026-02-06-payment-retries-adr]]'
```

Three rules govern them:

- Quote them. Unquoted, YAML reads `[[...]]` as a nested sequence.
- Use no relative paths. The namespace is flat, so `[[document-stem]]` resolves wherever
  the document lives. A `../` prefix breaks on the first reorganisation.
- Link only documents that exist. The `dangling` check finds the ones that do not.

In body prose, use neither wiki-links nor Markdown path links. Cite code by locator
instead, in backticks: `src/billing/retry.py:42`, commit `abc1234`, or
`vaultspec-core@0.1.59`. The `body-links` check enforces this.

The reason is direction. Vault documents cite code; code never cites the vault. Keeping
links out of body prose keeps the graph in one place, where the checks can see it.

## Values the tool writes

Four values are derived rather than authored. Writing one by hand is the only way to
make it lie.

`modified` is a last-modified stamp. Every mutating command refreshes it.

`body_hash` is a fingerprint of the body that `modified` attests. It appears in no
template, because it cannot exist before the body it hashes. It is what makes an
unstamped edit detectable: the `modified-stamp` check compares the live body against
this value and never consults file timestamps.

`body_schema` records which body structure the document follows, so the `body-sections`
check knows which sections to require.

`step_id`, on an execution record, is filled from the Step it was scaffolded against.

Change the body of a document by hand without restamping, and the check says so:

```
! .vault/exec/2026-02-04-editor-demo/2026-02-04-editor-demo-S01.md
  Stale modified stamp '2026-02-04'; the document body no longer matches its
  attested fingerprint (unstamped edit).
  fix: refresh to '2026-02-06' and re-attest the body
```

Run `vaultspec-core vault check all --fix` to restamp.

## Template placeholders

Templates carry two kinds of placeholder, and they are not interchangeable.

Author-replaced placeholders use curly braces and lowercase kebab-case: `{feature}`,
`{topic}`, `{title}`. Fill them in as you write.

Machine-filled placeholders use snake_case and are substituted by the command that
scaffolds the document:

| Placeholder       | Filled by                            |
| ----------------- | ------------------------------------ |
| `{heading}`       | `vaultspec-core vault add exec`      |
| `{step_id}`       | `vaultspec-core vault add exec`      |
| `{plan_stem}`     | `vaultspec-core vault add exec`      |
| `{scope_block}`   | `vaultspec-core vault add exec`      |
| `{document_list}` | `vaultspec-core vault feature index` |

If one of these survives into a committed document, the document was created by hand
rather than by the command that owns it. The `placeholders` check finds any `{...}` left
behind.

## Filenames

The command decides the filename. The patterns are worth recognising when you are
reading a directory listing:

| Document                        | Pattern                                         |
| ------------------------------- | ----------------------------------------------- |
| Top-level                       | `yyyy-mm-dd-{feature}-{type}.md`                |
| With a topic infix              | `yyyy-mm-dd-{feature}-{topic}-{type}.md`        |
| Execution record, `L1`          | `yyyy-mm-dd-{feature}-{step}.md`                |
| Execution record, `L2`          | `yyyy-mm-dd-{feature}-{phase}-{step}.md`        |
| Execution record, `L3` and `L4` | `yyyy-mm-dd-{feature}-{wave}-{phase}-{step}.md` |
| Phase summary                   | `yyyy-mm-dd-{feature}-{phase}-summary.md`       |
| Feature index                   | `{feature}.index.md`                            |

Narrative segments are lowercase kebab-case. Container identifiers keep their canonical
uppercase form: `W01`, `P02`, `S03`.

The topic infix exists for a feature that needs a second decision record or a second
piece of research. Pass `--topic` rather than inventing a filename; `adr`, `audit`,
`reference`, and `research` accept it, and nothing else does.

## Plan structure

A plan is the one document whose shape the tooling reads rather than only validates. Its
rows carry identifiers that execution records point back at, so the grammar is a
contract and not a convention.

### Tiers

The tier declared in frontmatter decides which containers exist:

| Tier | Structure                                                                |
| ---- | ------------------------------------------------------------------------ |
| `L1` | Steps only                                                               |
| `L2` | Phases above Steps                                                       |
| `L3` | Waves above Phases above Steps                                           |
| `L4` | An Epic frame above Waves, and a declared project-management association |

Choose by the complexity of the work, not by counting containers. A plan does not earn
`L3` by having enough rows to fill three Waves; it earns `L3` when the work genuinely
has three stages that must land in order.

Promote later with `vaultspec-core vault plan tier promote`. Promotion adds containers
and renumbers nothing.

### Row format

One row per unit of work:

```
- [ ] `W01.P02.S07` - Rewrite the retry backoff to read its ceiling from config; `src/billing/retry.py`.
```

The parts, in order: a two-state checkbox, the display path in backticks, a spaced
hyphen, an imperative-verb action, a semicolon, and the file scope in backticks.

Only two checkbox states exist. `[ ]` is open and `[x]` is closed. Nothing records "in
progress", because a row that is half done is a row that was too large.

Write plain ASCII hyphens. Em dashes and en dashes are rejected in plan bodies.

Wiki-links and Markdown links are forbidden in a plan body. The documents that authorise
the work go in the plan's `related:` frontmatter once, and every Step inherits that
chain. Per-row reference footers do not exist.

### Display paths

The identifier written in a row depends on the tier:

| Tier       | Step path     | Phase heading | Wave heading |
| ---------- | ------------- | ------------- | ------------ |
| `L1`       | `S07`         | none          | none         |
| `L2`       | `P02.S07`     | `P02`         | none         |
| `L3`, `L4` | `W01.P02.S07` | `W01.P02`     | `W01`        |

Display paths are computed from the current grouping. Move a Phase to another Wave and
every Step under it displays a new path, while its canonical identifier stays what it
always was.

### Identifiers

`S##`, `P##`, and `W##` are flat, per-document, append-only, and immutable.

The consequence worth internalising: **gaps are never reused**. Remove Step 7 and the
next Step added is 8, not 7. The number is retired with the row.

This is what makes the record durable. An execution record written months ago names
`S07`, and that name still points at the work it described, because no later edit could
hand `S07` to something else.

Route every identifier-affecting change through the commands rather than editing rows by
hand:

```
vaultspec-core vault plan step add <plan> --phase P02 --action "..." --scope "src/x.py"
vaultspec-core vault plan step check <plan> S07
vaultspec-core vault plan step remove <plan> S07
```

The parser tolerates a hand-edited row. The `vaultspec-core vault plan check` command
flags it, and identifier preservation is guaranteed only when the command performs the
mutation.

### One action, one row

N self-similar actions means N rows. Never collapse them into "for each handler, add the
header" or "across all callers, rename the flag".

The rule holds at every tier, and it is about verification rather than tidiness. A
collapsed row cannot be half closed, so its execution record cannot say which callers
were touched, and nothing catches the one that was missed.

## Where to go next

The [framework manual](./framework.md) covers the workflow these documents record.
[Verifying a workspace and a vault](./verification.md) covers the checks named on this
page and what each one proves.
