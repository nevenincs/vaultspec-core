---
name: vaultspec-write
description: Write an implementation plan of waves, phases, and steps. Use only after an ADR is approved.
---

# Plan writing skill (vaultspec-write)

Use this skill:

- To write the required implementation plan grounded with research and ADRs.
- To plan **non-trivial work, such as new features, complex auditing, or refactoring**.
- When the user explicitly asked to "write plan" or "draft Steps".

This skill **MUST always** be called after `vaultspec-adr` concludes with architectural
approval.

**Announce at start:** "I'm using the `vaultspec-write` skill to write the
implementation plan."

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
retirement ledger, and display-path consistency that hand edits cannot. Run
`vaultspec-core vault plan --help` for the full subcommand surface and
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

Full criteria, the row contract, identifier rules, and ordering rules are embedded as
markdown-comment hint blocks in `.vaultspec/rules/templates/plan.md`. The skill defers
to those canonical sources rather than restating them.

## Rules

- **Must reference research and ADRs**. Read these in full prior to writing the plan.

- Ensure no knowledge gap remains prior to writing the plan. Call the
  `vaultspec-research` skill if more information is needed.

- **Granularity:** Every Step is one Markdown bulleted checkbox row naming exactly one
  file or one cohesive area in inline backticks per the Step row contract embedded in
  the plan template. No per-row reference footers; authorizing documents go once in the
  plan's `related:` frontmatter.

- **Persistence:**

  - Plans: scaffold via
    `vaultspec-core vault add plan --feature {feature} --tier <L1..L4> --related <adr-stem>`;
    the CLI owns the filename (`.vault/plan/yyyy-mm-dd-{feature}-plan.md`) and the
    frontmatter; never hand-write either. Build the structure with the
    `vaultspec-core vault plan` verbs above, then author the prose sections
    (Description, Parallelization, Verification) as body edits.

  - Phase Summaries: tier-conditional `.vault/exec/yyyy-mm-dd-{feature}/...-summary.md`
    filenames (`yyyy-mm-dd-{feature}-{phase}-summary.md` at L2;
    `yyyy-mm-dd-{feature}-{wave}-{phase}-summary.md` at L3/L4).

  - Step Records: tier-conditional `.vault/exec/yyyy-mm-dd-{feature}/...md` filenames
    (`yyyy-mm-dd-{feature}-{step}.md` at L1; `yyyy-mm-dd-{feature}-{phase}-{step}.md` at
    L2; `yyyy-mm-dd-{feature}-{wave}-{phase}-{step}.md` at L3/L4).

## Frontmatter

The scaffold owns the frontmatter; the full schema is defined in the `vaultspec` rule.
Plan-specific requirements on top of the shared schema:

- **`related`** carries the AUTHORIZING documents (ADR, research, reference, prior plan)
  for every Step in the plan. Steps inherit this chain; per-row reference footers do not
  exist. `related` is required when the plan contains at least one Step row.

- **`tier`** is an unquoted scalar with value `L1`, `L2`, `L3`, or `L4`, set via the
  `--tier` flag at scaffold time and changed only through
  `vaultspec-core vault plan tier promote | demote`. Pre-existing plans without the
  field default to `L2`.

Verify after scaffolding with `vaultspec-core vault check all` rather than hand-editing
frontmatter.

## Workflow

- **Research**: Ensure vaultspec research agents have answered questions.

- **Linking**: Ensure the Plan uses `[[wiki-links]]` only in the `related:` frontmatter
  field. The plan body must remain free of wiki-links and markdown links per the
  embedded LINK RULES in the plan template.

- **Drafting**: If working with sub-agents, load the `vaultspec-writer` agent persona.
  Instruct it to "Create an implementation plan for `{feature}` based on
  `[[...-adr.md]]`. Use the template at `.vaultspec/rules/templates/plan.md` and conform
  to the embedded HIERARCHY AND TIERS, IDENTIFIERS AND ROW CONTRACT, and NO COMPRESSION
  hint blocks. The plan's tier (`L1`/`L2`/`L3`/`L4`) is already set in frontmatter by
  the `--tier` flag at scaffold time."

- **Review**: Present the saved Plan summary to the user before executing.

- **Provide an absolute link** and prompt the user:

  ```markdown
  The Plan is ready:
  [[yyyy-mm-dd-{feature}-plan.md]]

  Do you want to approve the Plan, or request changes?
  ```

- **Approval loop**: The user must explicitly approve the Plan. If changes are
  requested, load the `vaultspec-writer` agent persona again to make changes. If more
  research and grounding is required, use the appropriate vaultspec research skills and
  agents. Instruct them to "Revise the plan based on user feedback: `{feedback}`."
