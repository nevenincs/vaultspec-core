---
name: vaultspec-adr
description: Capture an architectural decision as an ADR in .vault/adr/. Use after research, before planning, when a significant design choice and its trade-offs must be recorded.
---

# ADR writing skill (vaultspec-adr)

Use this skill:

- After a `vaultspec-research` session has concluded with a recommendation.
- When multiple competing technical choices need a grounding document.
- When a significant architectural decision is made that affects the project's
  foundations, feature set, or development trajectory.
- To document the blast radius, "why", and "what" of major architectural choices.

**Announce at start:** "I'm using the `vaultspec-adr` skill to create a new ADR."

## Required steps

- **Read and use the template** at `.vaultspec/rules/templates/adr.md`; its embedded
  hint blocks govern the body structure.

- **Scaffold via the CLI:**
  `vaultspec-core vault add adr --feature {feature} --related <research-stem>`, then
  author the body prose in the scaffolded file. The CLI owns the filename
  (`.vault/adr/yyyy-mm-dd-{feature}-adr.md`) and the frontmatter; never hand-write
  either. The full frontmatter schema is defined in the `vaultspec` rule; verify after
  scaffolding with `vaultspec-core vault check all` rather than hand-editing
  frontmatter.

- **Read and link related Research from:**
  `.vault/research/yyyy-mm-dd-{feature}-research.md`.

- **Terminate if related research is not found** and prompt the user to first invoke
  `vaultspec-research`.

## Workflow

- **Derive from Research:** ADRs should always be preceded by a `vaultspec-research`
  session.

- **CRITICAL: you MUST always** present ADR findings as an interactive prompt for user
  approval. Without explicit user sign-off the ADR is considered null and void.

- **Draft the ADR using the `vaultspec-adr-researcher` agent persona**, which formalizes
  the research-backed decisions into ADR content and returns it for persistence into the
  scaffolded document (the `vaultspec-writer` persona's mandate is plan-only).

- Associate the ADR with `{feature}` based on the findings in `[[...-research.md]]`.

- **Supersession:** when a new ADR replaces an old one, run
  `vaultspec-core vault adr supersede` rather than editing status lines by hand; the
  verb records the `superseded_by:` back-pointer on the old ADR.

- **Linking:** Use `[[wiki-links]]` for references. DO NOT use `@ref` or
  `[label](path)`.
