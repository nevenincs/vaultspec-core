---
name: vaultspec-adr
description: >-
  Use this skill to persist Architecture Decision Records (ADRs) after
  completing research. ADRs document significant architectural choices,
  their context, and consequences.
---

# ADR: Architecture Decision Record Writing Skill

Use this skill:

- After a `vaultspec-research` session has concluded with a recommendation.

- When multiple competing technical choices need a grounding document.

- When a significant architectural decision is made that affects the project's
  foundations, feature set, or development trajectory.

- To document the blast radius, "why", and "what" of major architectural choices.

## Required steps

- **Announce at start:** "I'm using the `vaultspec-adr` skill to create a new ADR."
- **You MUST read and use the template** at `.vaultspec/rules/templates/adr.md`; its
  embedded hint blocks govern the body structure.
- **Scaffold via the CLI:**
  `vaultspec-core vault add adr --feature {feature} --related <research-stem>`, then
  author the body prose in the scaffolded file. The CLI owns the filename
  (`.vault/adr/yyyy-mm-dd-{feature}-adr.md`) and the frontmatter; never hand-write
  either.
- **Read and link related Research from:**
  `.vault/research/yyyy-mm-dd-{feature}-research.md`.
- **Terminate if related research is not found** and prompt user to first invoke
  `vaultspec-research`.

### Frontmatter & Tagging Mandate

The `vaultspec-core vault add` scaffold produces frontmatter conforming to this schema.
Verify it after scaffolding; report drift via `vaultspec-core vault check all` rather
than hand-editing frontmatter:

- **`tags`**: contains the required tag pair in a YAML list.

  - **Directory Tag**: Exactly `#adr`.
  - **Feature Tag**: Exactly one kebab-case `#{feature}` tag.
  - *Syntax:* `tags: ['#adr', '#{feature}']` (quoted strings in a list).

- **`related`**: a YAML list of quoted `'[[wiki-links]]'`, seeded from the `--related`
  flag at scaffold time.

  - *Constraint:* No relative paths (`../`), no bare strings, no `@ref`.

- **`date`**: `yyyy-mm-dd` format, set by the scaffold.

- **No `feature` key**: `tags:` exclusively identifies the feature.

## Workflow

- **Derive from Research:** ADRs should always be preceded by a `vaultspec-research`
  session.

- **CRITICAL: you MUST always** present adr findings as an interactive prompt for user
  approval. Without explicit user sign-off the ADR is considered null and void.

- **Draft ADR using the `vaultspec-adr-researcher` agent persona**, which formalizes the
  research-backed decisions into ADR content and returns it for persistence into the
  scaffolded document (the `vaultspec-writer` persona's mandate is plan-only).

- Associate ADR with `{feature}` based on the findings in `[[...-research.md]]`.

- **Linking:** Use `[[wiki-links]]` for references. DO NOT use `@ref` or
  `[label](path)`.
