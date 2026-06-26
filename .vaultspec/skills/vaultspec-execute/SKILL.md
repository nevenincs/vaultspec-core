---
name: vaultspec-execute
description: Execute an approved implementation plan, dispatching agent personas per step. Use when a plan document is ready to build.
---

# Plan execution skill (vaultspec-execute)

Use this skill:

- To begin the execution of an implementation plan.
- To ensure code is written by the appropriate agent.

**Announce at start:** "I'm using the `vaultspec-execute` skill to execute the
implementation plan."

## Required steps

- This skill MUST be invoked to execute an implementation plan located at
  `.vault/plan/yyyy-mm-dd-{feature}-plan.md`.

- Read and parse the Plan to understand the scope, complexity, and specific Steps.

- Read and parse all linked documents to understand the coding challenge.

- **Ground each Step in real code before editing.** Locate a Step's target in the live
  codebase before changing it - lead with `vaultspec-rag search "<intent>" --type code`,
  the fastest way to the right file - then read the epicenter or nearest existing
  analogue in full and confirm exact symbols with a targeted grep; for an extension,
  diff the requirements against the nearest analogue. Instruct every dispatched executor
  to do the same. Where `vaultspec-rag` is not installed, the `vaultspec-core` discovery
  verbs and grep carry the same sequence.

## Executor delegation

Assume the persona of a delegator.

- Use parallel sub-agents, or an autonomous agent team, to execute complex plans.

- Use the appropriate executor agent persona. When the work needs multiple specialists,
  coordinate them.

- Always instruct the coders to execute the current plan, and to read grounding
  research, ADRs, and the `[[...-plan.md]]`.

- Always name the tier-conditional entry point: instruct "Start with Step `S##`." at L1
  (Steps only), "Start with Phase `P##`." at L2, or the canonical display path (e.g.,
  `W01.P01`) at L3 / L4.

### Step execution and logging

- Execute the plan one Step at a time. Per the Step row contract embedded in the plan
  template, each Step is exactly one prompt-run plus one commit; the executor closes the
  row (`- [ ]` to `- [x]`) on completion.

- **One Step Record per completed Step.** The executor writes a Step Record to
  `.vault/exec/yyyy-mm-dd-{feature}/...md` for every completed Step (not per Phase).
  Scaffold the record with
  `vaultspec-core vault add exec --feature <tag> --step <S##> --related <plan-stem>`,
  then author the body prose. The verb machine-fills the tier-conditional filename from
  the plan's canonical display path (`yyyy-mm-dd-{feature}-{step}.md` at L1,
  `yyyy-mm-dd-{feature}-{phase}-{step}.md` at L2, and
  `yyyy-mm-dd-{feature}-{wave}-{phase}-{step}.md` at L3/L4) and the `step_id:`
  frontmatter field carrying the originating Step's canonical identifier (`S##`).

- **Coder or supervisor must read and use the template** at
  `.vaultspec/templates/exec-step.md`.

- **Frontmatter:** the scaffold owns the filename and frontmatter of every artifact
  (Step Record, Summary); the full schema is defined in the `vaultspec` rule. Verify
  with `vaultspec-core vault check all` rather than hand-editing.

### Mandatory code review

- After an executor completes a step (or the full plan), you MUST invoke the
  `vaultspec-code-review` skill or a relevant code-review skill.

- For code reviews, always use the `vaultspec-code-reviewer` persona to audit for
  safety, intent, and quality.

- If the reviewer identifies **CRITICAL** or **HIGH** issues, you MUST resolve them by
  loading an executor again before proceeding.

### Finalization and summary

- Once all implementation and review steps are complete (and the review passes), write
  the consolidated Phase Summary at `.vault/exec/yyyy-mm-dd-{feature}/...-summary.md`
  using `yyyy-mm-dd-{feature}-{phase}-summary.md` at L2 or
  `yyyy-mm-dd-{feature}-{wave}-{phase}-summary.md` at L3/L4.

- **Template**: You MUST read and use the template at
  `.vaultspec/templates/exec-summary.md`.

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
  `vaultspec-core vault plan check`.
