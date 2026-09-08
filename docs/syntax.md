# Document syntax

Create documents with `vaultspec-core vault add`; record execution with
`vaultspec-core vault exec log`, which creates the plan's ledger when needed.

## Who owns what

Frontmatter, field by field:

| Field         | Who changes it | How                                                                |
| ------------- | -------------- | ------------------------------------------------------------------ |
| `tags`        | The tool       | Set from `--feature` at scaffold. Do not add more.                 |
| `date`        | The tool       | Set at scaffold; the filename embeds the same date.                |
| `modified`    | The tool       | Refreshed by every command that writes the document.               |
| `body_schema` | The tool       | Records which body structure the document follows.                 |
| `body_hash`   | The tool       | A fingerprint of the body that `modified` attests.                 |
| `related`     | You            | `--related` when scaffolding, then `vault link add` and `remove`.  |
| `tier`        | You            | Through `vaultspec-core vault plan tier promote` or `tier demote`. |
| `generated`   | The tool       | Marks a file that is rebuilt rather than authored.                 |

Bodies, by document type:

| Body                             | Who changes it | How                                                          |
| -------------------------------- | -------------- | ------------------------------------------------------------ |
| Prose in any scaffolded document | You            | `vaultspec-core vault set-body`, or an editor plus a restamp |
| Rows in a plan                   | You            | `vaultspec-core vault plan` verbs only                       |
| Rows in a ledger                 | The tool       | `vaultspec-core vault exec log`                              |
| A feature index, whole file      | The tool       | `vaultspec-core vault feature index`                         |

Plan rows look like ordinary Markdown, but their identifiers connect planned work to
execution records. Change rows and checkboxes through the plan tools.

## Editing safely

Use `set-body` to replace prose and update `modified` and `body_hash`. By default, it
validates the result before writing and rejects changes with validation errors:

```bash
vaultspec-core vault set-body <document> --body-file new-body.md
vaultspec-core vault edit <document>              # body and frontmatter in one write
vaultspec-core vault rename <document> --to <new-stem>   # also re-points incoming links
```

If you edit in your own editor instead, the document's `body_hash` no longer matches its
body, and nothing has restamped `modified`. Run this afterwards:

```bash
vaultspec-core vault check all --fix
```

Review the changed files, then
[rerun validation](verification.md#check-records-before-committing).

Before enabling commit-time checks with `pre-commit install`, review
[hook behavior and project policy](framework.md#configure-project-integrations).
Installing `.pre-commit-config.yaml` alone does not activate the hooks.

## Frontmatter

Newly generated documents carry these six fields:

```yaml
---
tags:
  - '#plan'
  - '#payment-retries'
date: '2026-02-06'
modified: '2026-02-06'
body_schema: 'body-v2'
body_hash: 'sha256:...'
related:
  - '[[2026-02-06-payment-retries-adr]]'
---
```

Plans add `tier`; generated indexes add `generated`:

| Type  | Extra field | Holds                                              |
| ----- | ----------- | -------------------------------------------------- |
| plan  | `tier`      | The plan structure: `L1`, `L2`, `L3`, or `L4`      |
| index | `generated` | Always `true`; the file is rebuilt, never authored |

Execution ledgers link to their parent plan in `related`; each row carries its Step
identifier. See [execution logging](CLI.md#vaultspec-core-vault-exec-log).

ADRs also use `supersedes` and `superseded_by` for replacement relationships, maintained
by `vaultspec-core vault adr supersede`. Their decision status is in the body heading,
not a frontmatter field. Follow the
[decision lifecycle](framework.md#find-and-amend-an-adr) when changing it. Use the
owning commands for supported fields; don't invent metadata.

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

The feature tag is kebab-case and shared by that feature's records. Filtering for
`#payment-retries` finds its records; their links can lead to decisions and evidence
under other feature tags. A feature does not need every document type.

Use only the directory tag and the feature tag; `vault add --tags` rejects additional
tags.

## Linking

Put links between vault documents in `related:` as quoted Obsidian-style wiki-links:

```yaml
related:
  - '[[2026-02-06-payment-retries-research]]'
  - '[[2026-02-06-payment-retries-adr]]'
```

When creating a document, set links with `vaultspec-core vault add --related`.
Afterwards, use [link add](CLI.md#vaultspec-core-vault-link-add) or
[link remove](CLI.md#vaultspec-core-vault-link-remove).

- Quote wiki-links so YAML reads them as strings, not nested sequences.
- Store document stems without directories or `.md`: `[[document-stem]]`.
- Link only to existing documents. The `dangling` check reports unresolved links.

Plans link their governing ADRs, even across feature tags. Supporting evidence is
reachable through those ADRs; direct evidence links are optional. A decision-free plan
can have an empty `related` list. See
[choosing the route](framework.md#choose-the-route-for-your-task).

The `body-links` check rejects wiki-links and Markdown path links in body prose. Cite
code by locator instead, in backticks: `src/billing/retry.py:42`, commit `abc1234`, or
`vaultspec-core@0.1.59`.

Keep references one-way: vault documents cite code; source code must not cite vault
documents.

<p id="values-you-must-never-write-by-hand"></p>

## Generated metadata

The `modified-stamp` check compares the body against its stored `body_hash`, not
filesystem timestamps. Without a stored hash, it can't detect an unstamped body edit.

The `body-sections` check uses `body_schema` to check the document's sections. Newly
scaffolded documents use `body-v2`. See
[validation and repair](verification.md#check-records-before-committing).

## Template placeholders

Creation commands fill `{feature}` from `--feature` and `{title}` or `{topic}` from
`--title`. Complete remaining prose placeholders before committing.

| Placeholder       | Filled by                            |
| ----------------- | ------------------------------------ |
| `{plan_stem}`     | `vaultspec-core vault exec log`      |
| `{document_list}` | `vaultspec-core vault feature index` |

The `placeholders` check reports recognized tokens, date forms, and enum forms left in
body prose as errors. It skips comments, fenced code, and inline code except in
headings. It doesn't check every brace expression or fill missing content. See the
[check reference](CLI.md#vaultspec-core-vault-check) for commands and options.

## Filenames

Core generates filenames in these forms:

| Document           | Pattern                                  |
| ------------------ | ---------------------------------------- |
| Top-level          | `yyyy-mm-dd-{feature}-{type}.md`         |
| With a topic infix | `yyyy-mm-dd-{feature}-{topic}-{type}.md` |
| Ledger             | `yyyy-mm-dd-{feature}-ledger.md`         |
| Feature index      | `{feature}.index.md`                     |

Narrative segments are lowercase kebab-case. Ledgers use their parent plan's date and
feature in both the folder and filename:
`.vault/exec/2026-02-04-editor-demo/2026-02-04-editor-demo-ledger.md`.

For `adr`, `audit`, `reference`, and `research`, use
[vault add --topic](CLI.md#vaultspec-core-vault-add) to distinguish multiple records for
a feature.

## Plan structure

Edit plan rows with the [plan commands](CLI.md#vaultspec-core-vault-plan). Execution
ledgers reference the plan's Step identifiers.

### Tiers

The tier declared in frontmatter decides which containers exist. Use the smallest
structure that helps coordinate the work, not a tier based solely on file or worker
count:

| Tier | Structure                                                                |
| ---- | ------------------------------------------------------------------------ |
| `L1` | Steps only                                                               |
| `L2` | Phases above Steps                                                       |
| `L3` | Waves above Phases above Steps                                           |
| `L4` | An Epic frame above Waves, and a declared project-management association |

Change tiers with `vaultspec-core vault plan tier promote` or `tier demote`. Promotion
preserves canonical identifiers. See the
[plan command reference](CLI.md#vaultspec-core-vault-plan) for demotion and collapse
options.

### Row format

One row per cohesive, verifiable change. For an L1 plan:

```
- [ ] `S07` - Make retry backoff configurable and verify its limits; `src/billing, tests/billing`.
```

Reading that row left to right:

| Part                       | Example                               |
| -------------------------- | ------------------------------------- |
| Checkbox, two states only  | `- [ ]`                               |
| Display path, in backticks | `` `S07` ``                           |
| Spaced ASCII hyphen        | `-`                                   |
| Imperative-verb action     | `Make retry backoff configurable ...` |
| Semicolon                  | `;`                                   |
| File scope, in backticks   | `` `src/billing, tests/billing` ``    |
| Trailing period            | `.`                                   |

`[ ]` is open and `[x]` is closed. The format has no in-progress marker.

Write plain ASCII hyphens. The `PLAN060` rule rejects em-dashes and en-dashes anywhere
in a plan: body, headings, frontmatter, and comment hints. `vault plan check --fix`
replaces them with an ASCII spaced hyphen.

### Display paths

The identifier written in a row depends on the tier:

| Tier       | Step path     | Phase heading | Wave heading |
| ---------- | ------------- | ------------- | ------------ |
| `L1`       | `S07`         | none          | none         |
| `L2`       | `P02.S07`     | `P02`         | none         |
| `L3`, `L4` | `W01.P02.S07` | `W01.P02`     | `W01`        |

Display paths reflect the current grouping. Moving a Phase to another Wave changes its
Steps' display paths without changing their canonical identifiers.

### Identifiers

Canonical identifiers (`S##`, `P##`, `W##`) are numbered per plan and stay stable across
moves and tier changes. A Step's number is independent of its Phase.

Removed identifiers aren't reused. The next Step number exceeds the highest live or
retired Step number.

Route every identifier-affecting change through the commands:

```
vaultspec-core vault plan step add <plan> --phase P02 --action "..." --scope "src/x.py"
vaultspec-core vault plan step check <plan> S07
vaultspec-core vault plan step remove <plan> S07
```

Run `vaultspec-core vault plan check <plan>` to check plan conventions;
`vault check all` does not include them. See
[plan commands](CLI.md#vaultspec-core-vault-plan) for options.

Duplicated canonical identifiers make ledger references ambiguous. Review the execution
records before repairing a conflict; validation cannot determine which Step an existing
record meant.

<p id="one-action-one-row"></p>

### Step size

Keep implementation and its verification together when they form one cohesive change.
Split work when it needs an independent completion state, not for every file or edit.
Step size is a planning judgment; no structural check decides it.

## Where to go next

The [framework manual](./framework.md) covers the workflow these documents record.
[Verifying a workspace and a vault](./verification.md) covers the checks named on this
page and what each one proves.
