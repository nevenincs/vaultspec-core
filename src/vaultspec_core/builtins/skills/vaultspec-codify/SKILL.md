---
name: vaultspec-codify
description: >-
  Use this skill to promote durable lessons from a completed audit
  or ADR into a project-shared rule under `.vaultspec/rules/rules/`
  (the directory the CLI's `vaultspec-core spec rules add` writes to today; the
  planned `--scope project` flag will move authored rules under
  `.vaultspec/rules/rules/project/`). Codification is the
  discretionary sixth phase of the pipeline; engage only when a
  lesson satisfies the three durability criteria.
---

# Codify: Project Rule Authoring Skill

Use this skill:

- After a `vaultspec-code-review` session, a `vaultspec-execute` run, or an `<Audit>`
  document surfaces a lesson that must bind future agents across sessions.

- When the lesson is constraint-shaped (renderable as "always X" or "never Y") and
  project-bound (specific to this project's conventions, not generic engineering
  advice).

- When no existing rule already covers the intent.

Do NOT use this skill:

- On the first encounter with a constraint. Wait until the constraint has held across at
  least one full execution cycle.

- For implementation detail of a single feature. That belongs in `<Reference>`, not in a
  project rule.

- For generic engineering advice. That belongs in external documentation, not in this
  project's rules.

## Required steps

- **Announce at start:** "I'm using the `vaultspec-codify` skill to promote a durable
  lesson into a project rule."

- **Verify the three durability criteria** explicitly. Restate each one with the source
  audit / ADR evidence that satisfies it. If any criterion fails, abort and explain.

- **Search for existing coverage** before authoring:

  - `vaultspec-core spec rules list`
  - `vaultspec-core spec rules show <candidate-name>`

  If an existing rule partially covers the intent, edit it in place via
  `vaultspec-core spec rules edit <name>` rather than producing a near-duplicate.

- **Choose a kebab-case slug** that names the constraint's subject rather than the
  failure that prompted it. Slug examples: `harbor-notes-runtime-data` (subject: runtime
  data), `destructive-verbs-need-dry-run` (subject: destructive verbs). Slug
  counter-examples: `audit-finding-23`, `joan-said-so`.

- **Scaffold the rule via the CLI**: `vaultspec-core spec rules add <rule-name>`. Do NOT
  write the file directly; the CLI ensures path discipline and metadata correctness.

- **Author the rule body** using the three-section shape: **Rule**, **Why**, **How**.
  See the body template below.

- **Reference the source** audit document or ADR by stem in backticks in the **Why**
  section. The framework's planned `derived_from:` frontmatter field will later carry
  the same reference in structured form.

- **Verify the result** with `vaultspec-core spec rules show <name>` and read the rule's
  wording back to the dispatcher. The wording is the contract; do not skip the
  verification read.

- **Terminate if the source audit / ADR was not located** and prompt the user to first
  complete `vaultspec-code-review` or the audit-producing skill.

### Body template

```markdown
---
name: <kebab-case-slug>
---

# <Title naming the constraint>

## Rule

<One imperative sentence: always X, or never Y.>

## Why

<Two or three sentences. Cite the source audit or ADR by stem in
backticks. Name the failure mode this rule prevents.>

## How

- Good: <concrete worked example of the rule applied.>
- Bad: <concrete worked example of the rule violated.>
```

### Frontmatter & tagging mandate

Project rule files use the `vaultspec-core spec rules` schema, not the `.vault/` schema:

- **`name`**: MUST match the kebab-case slug used in the filename.

- No `tags:`, no `date:`, no `related:` field on rule files. Project rules are not part
  of the `.vault/` paper trail; they are the project's standing policy. The audit / ADR
  back-pointer lives in the rule body (Why section) until the planned `derived_from:`
  frontmatter field lands.

## Supersession discipline

When an existing rule no longer holds:

- **Edit in place** if the constraint shifted at the margins.
- **Supersede** with a new rule if the constraint changed at the center. Add a
  `## Status` section to both rule bodies: the prior rule's Status names the successor's
  slug, and the new rule's Status names the rule it supersedes. Do NOT silently delete;
  once teammates are aware, remove the prior rule via
  `vaultspec-core spec rules remove <name>`.

The supersession event is itself a project-level signal; record it in the audit document
that surfaced the new constraint.

## Persistence

- **Output location:** today the CLI scaffold path writes to
  `.vaultspec/rules/rules/<rule-name>.md` alongside the framework's builtin rules.
  Project-authored rules are distinguished from builtins by name convention (builtins
  use the `*.builtin.md` suffix; authored rules do not). A planned `--scope project`
  flag on `vaultspec-core spec rules add` will separate authored rules under a dedicated
  subdirectory; see the sibling `cli-spec-crud-parity` ADR.

- **Sharing policy:** project rules under `.vaultspec/rules/` are team-shared by the
  framework's policy; teammates inherit the rule on next clone or sync.

- **Report:** at the end of the skill, return the rule's absolute path, the source audit
  / ADR stems, and a one-sentence summary of the codified constraint.

## Workflow

- **Derive from a completed phase.** Codification follows review, not research or
  planning. A rule authored from an unfinished feature has nothing to bind on.

- **Dispatch through `vaultspec-codifier`** persona when the scaffolding workload
  warrants a dedicated agent. For single-rule codifications the dispatcher may execute
  the skill inline.

- **Cross-check discoverability.** A fresh-eyes agent loading
  `vaultspec-core spec rules list` should see the new rule and understand its scope from
  the name alone. If the slug name fails the look-and-know test, rename before reporting
  done.
