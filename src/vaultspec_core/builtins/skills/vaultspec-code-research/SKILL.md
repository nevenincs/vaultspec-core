---
name: vaultspec-code-research
description: >-
  Skill for grounding coding tasks by researching projects, code snippets,
  reference implementations. Highly recommended for complex feature
  implementation, or where documentation coverage is insufficient and
  direct source-code referencing is required.
---

# Code Research

Use this skill:

- When auditing, researching, or implementing a specific technical implementation.

- When you need to identify a reference project.

- When you need source references that show how another project implements a feature.

- To avoid missing implementation details.

- To ground and de-risk complex coding tasks with actual code.

Invoke when `vaultspec-research` -> `vaultspec-adr` -> `vaultspec-write` explicitly
requires direct code referencing.

## Required steps

- **Announce at start:** "I'm using the `vaultspec-code-research` skill to find out how
  `{Reference}` implements `{Feature}`."

- **You MUST read and use the template** at `.vaultspec/rules/templates/reference.md`;
  its embedded hint blocks govern the body structure.

- **Load the `vaultspec-reference-auditor` agent persona** for the focused code deep
  dives. Instruct it to locate and audit the `{Feature}` implementation in the reference
  codebase; it returns its findings to you for persistence.

- **Persist findings:** scaffold the reference document with
  `vaultspec-core vault add reference --feature {feature}`, then author the findings as
  body prose. The CLI owns the filename
  (`.vault/reference/yyyy-mm-dd-{feature}-reference.md`) and the frontmatter; never
  hand-write either.

### Frontmatter & Tagging Mandate

The `vaultspec-core vault add` scaffold produces frontmatter conforming to this schema.
Verify it after scaffolding; report drift via `vaultspec-core vault check all` rather
than hand-editing frontmatter:

- **`tags`**: contains the required tag pair in a YAML list.

  - **Directory Tag**: Exactly `#reference`.
  - **Feature Tag**: Exactly one kebab-case `#{feature}` tag.
  - *Syntax:* `tags: ['#reference', '#{feature}']` (quoted strings in a list).

- **`related`**: a YAML list of quoted `'[[wiki-links]]'`, seeded from the `--related`
  flag at scaffold time.

  - *Constraint:* No relative paths (`../`), no bare strings, no `@ref`.

- **`date`**: `yyyy-mm-dd` format, set by the scaffold.

- **No `feature` key**: `tags:` exclusively identifies the feature.

### Research & Audit

Perform focused code deep dives.

Coordinate the loaded persona and any supporting agents to:

- Locate the code snippets and files.
- Analyze implementation patterns and architecture.
- Persist a Reference blueprint into the scaffolded document's body. If the document
  exists already, assess and update its body prose.

### Implementation Plan

You MUST check if an implementation exists already. If it does:

- Do our findings alter the implementation? If so, report back to the user.
- Report possible issues or drift and leave notes in the Plan that reference the
  `{Feature}` audit.
