---
name: vaultspec-research
description: >-
  Use this skill for structured research and brainstorming when unsure how to
  proceed with a complex feature, refactor, or debugging task and options need
  exploring before implementation.
---

# Research & Brainstorm Skill (vaultspec-research)

When to use this skill:

- Before implementing non-trivial features.
- When unsure about major design decisions.
- Before refactors with unclear scope.
- Before debugging complex issues.
- When you need user input on design options.

**Announce at start:** "I'm using the `vaultspec-research` skill to conduct structured
research and brainstorming."

**Persist findings:** scaffold the research artifact with
`vaultspec-core vault add research --feature {feature}`, then author the findings as
body prose in the scaffolded file. The CLI owns the filename
(`.vault/research/yyyy-mm-dd-{feature}-research.md`) and the frontmatter; never
hand-write either.

Load the `vaultspec-adr-researcher` agent persona for focused work. When the task
benefits from multiple researchers, load the generic `vaultspec-researcher` agent
persona for the additional research threads and coordinate them through the host
environment rather than assuming a shipped MCP team-thread runtime. Instruct each
researcher to "Conduct research on `{topic}`." and write the returned findings into the
scaffolded document's body.

## Template

- You MUST read and use the template at `.vaultspec/rules/templates/research.md`; its
  embedded hint blocks govern the body structure.

### Frontmatter & Tagging Mandate

The `vaultspec-core vault add` scaffold produces frontmatter conforming to this schema.
Verify it after scaffolding; report drift via `vaultspec-core vault check all` rather
than hand-editing frontmatter:

- **`tags`**: contains the required tag pair in a YAML list.

  - **Directory Tag**: Exactly `#research`.
  - **Feature Tag**: Exactly one kebab-case `#{feature}` tag.
  - *Syntax:* `tags: ['#research', '#{feature}']` (quoted strings in a list).

- **`related`**: a YAML list of quoted `'[[wiki-links]]'`, seeded from the `--related`
  flag at scaffold time.

  - *Constraint:* No relative paths (`../`), no bare strings, no `@ref`.

- **`date`**: `yyyy-mm-dd` format, set by the scaffold.

- **No `feature` key**: `tags:` exclusively identifies the feature.

## Workflow

- Research & brainstorm might be followed by:
  - User approval -> proceed with `vaultspec-adr` to create and persist ADR.
  - No approval -> prompt user to refine goal/constraints and re-run research.

## Artifact Linking

- Any persisted markdown files must be linked against other persisted documents using
  `[[wiki-links]]`.

- DO NOT use `@ref` style links.

- DO NOT use `[label](path)` style links for internal wiki pages.
