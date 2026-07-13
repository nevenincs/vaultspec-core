---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S118
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# add the shared persona frontmatter schema the eleven top-level personas carry (D15)

## Scope

- `src/vaultspec_core/builtins/skills/vaultspec-documentation/agents/editorial-reviewer.md`

## Description

- Add the four-field persona frontmatter schema (description, tier, mode, tools) the
  eleven top-level personas under `src/vaultspec_core/builtins/agents/` carry
- Choose description "Context-free editorial reviewer. Judges a document purely on the
  merit of its writing against the prose style rules and returns located, rule-grounded
  findings with a verdict.", tier STANDARD, mode read-only, tools Read
- Format the agent with mdformat at wrap 88

## Outcome

The editorial reviewer agent now declares the same frontmatter schema every top-level
persona carries, per decision D15. The values follow the agent's own contract: it reads
its prose-style rules reference and the document under review, mutates nothing, and
returns findings only, so mode is read-only with Read as the single tool; the
rule-grounded evaluation matches the STANDARD tier. Both embedded documentation agents
(this one and the wireframe agent from P08.S117) now carry frontmatter, closing the
research finding that they alone among personas had none.

## Notes

None.
