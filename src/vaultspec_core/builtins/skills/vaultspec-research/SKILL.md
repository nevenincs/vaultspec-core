---
name: vaultspec-research
description: Explore an unfamiliar problem and weigh options before committing. Use when unsure how to approach a complex feature, refactor, or bug.
---

# Research and brainstorm skill (vaultspec-research)

Use this skill:

- Before implementing non-trivial features.
- When unsure about major design decisions.
- Before refactors with unclear scope.
- Before debugging complex issues.
- When you need user input on design options.

**Announce at start:** "I'm using the `vaultspec-research` skill to conduct structured
research and brainstorming."

## Required steps

- **Ground in existing intent first.** Before exploring options, retrieve what the
  project already decided: `vaultspec-rag search "<intent>" --type vault` surfaces the
  ADRs, audits, and prior research that bind this area, and
  `vaultspec-rag search "<intent>" --type code` locates the implementation sites that
  match semantically. Read the records this surfaces and check for overlap before adding
  new findings. Fall back to `vaultspec-core vault list` and grep when `vaultspec-rag`
  is not installed.

- **Read and use the template** at `.vaultspec/rules/templates/research.md`; its
  embedded hint blocks govern the body structure.

- **Load the `vaultspec-adr-researcher` agent persona** for focused work. When the task
  benefits from multiple researchers, load the generic `vaultspec-researcher` agent
  persona for the additional research threads and coordinate them through the host
  environment. Instruct each researcher to "Conduct research on `{topic}`." and write
  the returned findings into the scaffolded document's body.

- **Persist findings:** scaffold the research artifact with
  `vaultspec-core vault add research --feature {feature}`, then author the findings as
  body prose in the scaffolded file. The CLI owns the filename
  (`.vault/research/yyyy-mm-dd-{feature}-research.md`) and the frontmatter; never
  hand-write either. The full frontmatter schema is defined in the `vaultspec` rule;
  verify after scaffolding with `vaultspec-core vault check all` rather than
  hand-editing frontmatter.

## Workflow

- Research and brainstorm might be followed by:
  - User approval -> proceed with `vaultspec-adr` to create and persist the ADR.
  - No approval -> prompt the user to refine goal and constraints, then re-run research.

## Artifact linking

- Persisted documents reference each other with quoted `'[[wiki-links]]'` in the
  `related:` frontmatter field.
- DO NOT use `@ref` style links.
- DO NOT use `[label](path)` style links for internal wiki pages.
