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

Invoke when `vaultspec-research` -> `vaultspec-adr` -> `vaultspec-write-plan` explicitly
requires direct code referencing.

## Required steps

- **Announce at start:** "I'm using the `vaultspec-code-research` skill to find out how
  `{Reference}` implements `{Feature}`."

- Use appropriate focused agents when available. Instruct them to locate and audit the
  `{Feature}` implementation in the reference codebase.

- **Must persist findings** to `.vault/reference/yyyy-mm-dd-{feature}-reference.md`.

### Research & Audit

Perform focused code deep dives.

Coordinate the agents to:

- Locate the code snippets and files.
- Analyze implementation patterns and architecture.
- Persist a Reference blueprint to `.vault/reference/yyyy-mm-dd-{feature}-reference.md`.
  If file exists already, assess and update it.

### Implementation Plan

You MUST check if an implementation exists already. If it does:

- Do our findings alter the implementation? If so, report back to the user.
- Report possible issues or drift and leave notes in the Plan that reference the
  `{Feature}` audit.
