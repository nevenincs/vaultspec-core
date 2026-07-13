---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S117
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# add the shared persona frontmatter schema the eleven top-level personas carry (D15)

## Scope

- `src/vaultspec_core/builtins/skills/vaultspec-documentation/agents/wireframe-agent.md`

## Description

- Add the four-field persona frontmatter schema (description, tier, mode, tools) the
  eleven top-level personas under `src/vaultspec_core/builtins/agents/` carry
- Choose description "Fresh-eyes documentation wireframe evaluator. Assumes zero
  project knowledge, judges a proposed document outline against the Diataxis framework,
  and returns findings only.", tier STANDARD, mode read-only, tools Read
- Format the agent with mdformat at wrap 88
- Run the automation-contract, template-annotation, CLI-language, and agents-render
  test set: 85 passed

## Outcome

The wireframe agent now declares the same frontmatter schema every top-level persona
carries, per decision D15. The values follow the agent's own contract: it consults its
Diataxis rules reference and the outline it is handed, mutates nothing, and returns
findings as its final message, so mode is read-only with Read as the single tool; the
evaluation work is judgment-shaped but architecturally bounded, matching the STANDARD
tier the researcher and docs-curator personas occupy.

## Notes

The duplicated mandatory-read instruction and the square-bracket placeholder in the
same file are the scope of P08.S119 and were left untouched here.
