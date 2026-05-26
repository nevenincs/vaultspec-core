---
name: vaultspec-write
description: >-
  Use this skill to write implementation plans, Step flows. It must be
  explicitly called after a vaultspec-adr skill has yielded an approved ADR
  document.
---

# Write Implementation Skill

Use this skill to:

- Write the required implementation plan grounded with research and ADRs.
- plan **non-trivial work, such as new features, complex auditing, or refactoring**.
- when user explicitly asked to "write plan" or "draft Steps".

This skill **MUST always** be called after `vaultspec-adr` concludes with architectural
approval.

## Important

- If part of the `vaultspec-research` -> `vaultspec-adr` flow, this skill **MUST** be
  provided with the relevant Research and ADR documents.

- If invoked standalone, you must locate or request relevant context.

## CLI usage mandate

Plan documents authored by this skill MUST be manipulated via the
`vaultspec-core vault plan` CLI rather than by hand-editing the markdown body. The CLI
is the canonical surface for every identifier-affecting change. The verbs are:

- `vaultspec-core vault plan step add | insert | edit | move | remove`
- `vaultspec-core vault plan step check | uncheck | toggle` (state)
- `vaultspec-core vault plan phase add | insert | edit | move | renumber | remove`
- `vaultspec-core vault plan wave add | insert | edit | move | remove`
- `vaultspec-core vault plan epic intent show | edit` (L4 only)
- `vaultspec-core vault plan tier show | promote | demote`

The CLI guarantees canonical-identifier preservation, gap-no-reuse via a hidden
retirement ledger, and display-path consistency that hand edits cannot. See the CLI ADR
(`2026-05-06-plan-hardening-adr`) for the full subcommand contract and
`vaultspec-core vault plan check` for the validator that backs it.

## Hierarchy and tiers

The plan hierarchy is `Epic > Wave > Phase > Step`. Plans declare their complexity tier
(`L1`, `L2`, `L3`, or `L4`) in frontmatter; the tier determines which structural
containers exist:

- `L1`: Steps only.
- `L2`: Phases above Steps.
- `L3`: Waves above Phases above Steps.
- `L4`: Epic above Waves above Phases above Steps; an external project-management
  association is declared in the Epic intent block.

Full criteria, the row contract, identifier rules, and ordering rules are specified in
the plan-hardening convention ADR and embedded as markdown-comment hint blocks in
`.vaultspec/rules/templates/plan.md`. The skill defers to those canonical sources rather
than restating them.

## Rules

- **Announce:** Explicitly state you are starting the planning phase.

- **Must reference research and ADRs**. Read these in full prior to writing the plan.

- Ensure no knowledge gap remains prior to writing plan. Call vaultspec- research skills
  if more information is needed.

- **Granularity:** Every Step is one Markdown bulleted checkbox row naming exactly one
  file or one cohesive area in inline backticks per the Step row contract embedded in
  the plan template. No per-row reference footers; authorising documents go once in the
  plan's `related:` frontmatter.

- **Persistence:**

  - Plans: `.vault/plan/yyyy-mm-dd-{feature}-plan.md`

  - Phase Summaries: tier-conditional `.vault/exec/yyyy-mm-dd-{feature}/...-summary.md`
    filenames (`yyyy-mm-dd-{feature}-{phase}-summary.md` at L2;
    `yyyy-mm-dd-{feature}-{wave}-{phase}-summary.md` at L3/L4).

  - Step Records: tier-conditional `.vault/exec/yyyy-mm-dd-{feature}/...md` filenames
    (`yyyy-mm-dd-{feature}-{step}.md` at L1; `yyyy-mm-dd-{feature}-{phase}-{step}.md` at
    L2; `yyyy-mm-dd-{feature}-{wave}-{phase}-{step}.md` at L3/L4).

## Template

- You MUST read and use the template at `.vaultspec/rules/templates/plan.md`.

### Frontmatter & Tagging Mandate

Every document MUST strictly adhere to the following schema:

- **`tags`**: MUST contain the required tag pair in a YAML list.

  - **Directory Tag**: Exactly `#plan`.
  - **Feature Tag**: Exactly one kebab-case `#{feature}` tag.
  - _Syntax:_ `tags: ['#plan', '#feature']` (Must be quoted strings in a list).

- **`related`**: MUST be a YAML list of quoted `'[[wiki-links]]'`.

  - _Constraint:_ No relative paths (`../`), no bare strings, no `@ref`.
  - _For plan documents:_ `related` carries the AUTHORISING documents (ADR, research,
    reference, prior plan) for every Step in the plan. Steps inherit this chain; per-row
    reference footers do not exist. `related` is required when the plan contains at
    least one Step row.

- **`date`**: MUST use `yyyy-mm-dd` format.

- **`tier`** (plan documents only): MUST be present as an unquoted scalar with value
  `L1`, `L2`, `L3`, or `L4`. Pre-existing plans without the field default to `L2`; the
  writer adds the field on first edit.

- **No `feature` key**: Use `tags:` exclusively for feature identification.

## Workflow

- **Research**: Ensure vaultspec research agents have answered questions.

- **Linking**: Ensure the Plan uses `[[wiki-links]]` only in the `related:` frontmatter
  field. The plan body must remain free of wiki-links and markdown links per the
  embedded LINK RULES in the plan template.

- **Drafting**: If working with sub-agents, load the `vaultspec-writer` agent persona.
  Instruct it to "Create an implementation plan for `{feature}` based on
  `[[...-adr.md]]`. Use the template at `.vaultspec/rules/templates/plan.md` and conform
  to the embedded HIERARCHY AND TIERS, IDENTIFIERS AND ROW CONTRACT, and NO COMPRESSION
  hint blocks. Declare the plan's tier (`L1`/`L2`/`L3`/`L4`) in frontmatter."

- **Review**: Present the saved Plan summary to the user before executing.

- **Provide an absolute link** and prompt user:

  ```markdown
  The Plan is ready:
  [[yyyy-mm-dd-{feature}-plan.md]]

  Do you want to approve the Plan, or request changes?
  ```

- **Approval Loop**: User must explicitly approve the Plan. If changes are requested,
  load the `vaultspec-writer` agent personaa again to make changes. If more research and
  grounding is required, use the appropriate vaultspec research skills and agents.
  Instruct them to "Revise the plan based on user feedback: `{feedback}`."
