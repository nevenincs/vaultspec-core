---
name: vaultspec-execute
description: >-
  Skill to execute implementation plans. Loads specialized agent personas for
  focused work, or coordinates multiple personas through the host environment
  for complex multi-agent execution. Use when you have a plan document to
  execute.
---

# Implementation Plan: Code Writing Skill

Use this skill:

- To begin the execution of an implementation `plan`.
- To ensure code is written by the appropriate agent.

## Required Steps

- This skill MUST be invoked to execute an implementation `.vault/plan` located at
  `.vault/plan/yyyy-mm-dd-{feature}-plan.md`.

- Read and parse the Plan to understand the scope, complexity, and specific Steps

- Read and parse all linked documents to understand the coding challenge.

## Executor Delegation

Assume the persona of a delegator.

- Use parallel sub-agents, or autonomous agent team to execute complex plans.

- Use appropriate executor agent persona. When the work needs multiple specialists,
  coordinate them.

- Always instruct the coders to execute the current plan, and to read grounding
  research, ADRs, and the `[[...-plan.md]]`.

- Always instruct to "Start with Phase `P##`." (or the canonical display path, e.g.,
  `W01.P01`, at L3 / L4).

### Step Execution & Logging

- Execute the plan one Step at a time. Per the convention ADR's Step row contract, each
  Step is exactly one prompt-run plus one commit; the executor closes the row (`- [ ]`
  to `- [x]`) on completion.

- **One Step Record per completed Step.** The executor writes a Step Record to
  `.vault/exec/yyyy-mm-dd-{feature}/...md` for every completed Step (not per Phase). Use
  the tier-conditional filename from the plan's canonical display path:
  `yyyy-mm-dd-{feature}-{step}.md` at L1, `yyyy-mm-dd-{feature}-{phase}-{step}.md` at
  L2, and `yyyy-mm-dd-{feature}-{wave}-{phase}-{step}.md` at L3/L4. The originating
  Step's canonical identifier (`S##`) is recorded in the Step Record's `step_id:`
  frontmatter field.

- **Coder or supervisor must read and use the template** at
  `.vaultspec/rules/templates/exec-step.md`.

### Frontmatter & Tagging Mandate (Artifacts)

Every artifact (Step Record, Summary, Review) MUST strictly adhere to the following
schema:

- **`tags`**: MUST contain the required tag pair in a YAML list.

  - **Directory Tag**: Exactly `#exec`.
  - *Feature Tag:* Exactly one kebab-case `#{feature}` tag.
  - *Syntax:* `tags: ['#exec', '#feature']` (Must be quoted strings in a list).

- **`related`**: MUST be a YAML list of quoted `'[[wiki-links]]'`.

  - *Constraint:* No relative paths (`../`), no bare strings, no `@ref`.

- **`date`**: MUST use `yyyy-mm-dd` format.

- **No `feature` key**: Use `tags:` exclusively for feature identification.

### Mandatory Code Review

- After an executor completes a step (or the full plan), you MUST invoke the
  `vaultspec-code-review` skill or a relevant code-review skill.

- For code reviews, always use the `vaultspec-code-reviewer` persona to audit for
  safety, intent, and quality.

- If the reviewer identifies **CRITICAL** or **HIGH** issues, you MUST resolve them by
  loading an executor again before proceeding.

### Finalization & Summary

- Once all implementation and review steps are complete (and the review passes), write
  the consolidated Phase Summary at `.vault/exec/yyyy-mm-dd-{feature}/...-summary.md`
  using `yyyy-mm-dd-{feature}-{phase}-summary.md` at L2 or
  `yyyy-mm-dd-{feature}-{wave}-{phase}-summary.md` at L3/L4.

- **Template**: You MUST read and use the template at
  `.vaultspec/rules/templates/exec-summary.md`.

- Present the final findings, including modified files and safety status, to the user.

## Requirements

- **Autonomy**: Do not ask for confirmation between steps unless a significant
  unforeseen blocker occurs.

- **Integrity**: Ensure the safety audit is never skipped.

- **Traceability**: All changes must be mapped to their respective Step Records.

- **L4 plans**: When executing an `L4` plan, the execute skill respects the
  project-management association declared in the plan's `## Epic intent` block prose.
  Wave-completion and Epic-completion progress are reported against that external
  artifact (milestone, project board, roadmap entry) at Wave boundaries.

- **CLI usage mandate**: Executors MUST update Step state via
  `vaultspec-core vault plan step check` (close),
  `vaultspec-core vault plan step uncheck` (re-open), or
  `vaultspec-core vault plan step toggle` rather than hand-editing the checkbox glyph.
  The CLI guarantees idempotent state transitions and consistent display-path
  recomputation; hand edits bypass these guarantees and are flagged by
  `vaultspec-core vault plan check`. See the CLI ADR (`2026-05-06-plan-hardening-adr`).
